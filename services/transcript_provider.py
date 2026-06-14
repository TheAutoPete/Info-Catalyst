import inspect
import importlib
import json
import os
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import requests
import httpx
from openai import OpenAI

import config
from youtube_transcript_api import (
    IpBlocked,
    NoTranscriptFound,
    RequestBlocked,
    TranscriptsDisabled,
    YouTubeTranscriptApi,
)


config = importlib.reload(config)
OPENAI_API_KEY = getattr(config, "OPENAI_API_KEY", None)
OPENAI_TRANSCRIPTION_MODEL = getattr(config, "OPENAI_TRANSCRIPTION_MODEL", "whisper-1")
OPENAI_USE_SYSTEM_PROXY = getattr(config, "OPENAI_USE_SYSTEM_PROXY", False)


class TranscriptError(RuntimeError):
    def __init__(self, message: str, debug_messages: tuple[str, ...] = ()):
        super().__init__(message)
        self.debug_messages = debug_messages


LANGUAGE_PRIORITY = ("zh-TW", "zh-Hant", "zh-Hans", "zh-CN", "zh", "en")
TRANSLATION_TARGETS = {
    "en": "English",
}
YOUTUBE_PROXY_DEBUG_URL = "https://www.youtube.com/watch?v={video_id}"
YTDLP_TRANSCRIPT_CACHE_DIR = Path("reports") / "transcript-cache"
YTDLP_AUDIO_CACHE_DIR = Path("reports") / "audio-cache"


@dataclass(frozen=True)
class TranscriptMetadata:
    language: str
    language_code: str
    is_generated: bool
    is_translatable: bool
    translation_languages: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    @property
    def kind(self) -> str:
        return "generated" if self.is_generated else "manual"

    @property
    def display_label(self) -> str:
        translatable = ", translatable" if self.is_translatable else ""
        return f"{self.language_code} - {self.language} ({self.kind}{translatable})"


@dataclass(frozen=True)
class TranscriptOptions:
    video_id: str
    available_transcripts: tuple[TranscriptMetadata, ...]
    selected_transcript: TranscriptMetadata | None
    debug_messages: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class TranscriptResult:
    text: str
    video_id: str
    available_transcripts: tuple[TranscriptMetadata, ...]
    selected_transcript: TranscriptMetadata
    requested_translation: str | None = None
    item_count: int = 0
    start_seconds: float | None = None
    end_seconds: float | None = None
    source_type: str = "youtube"
    transcript_provider: str = "youtube_transcript_api"
    debug_messages: tuple[str, ...] = field(default_factory=tuple)


def get_transcript_options(video_id: str) -> TranscriptOptions:
    debug_messages = _build_proxy_debug_messages(video_id)
    try:
        transcript_list = _youtube_transcript_api().list(video_id)
        transcripts = tuple(transcript_list)
        available_transcripts = tuple(_metadata_from_transcript(item) for item in transcripts)
        selected_transcript = _metadata_from_transcript(_select_transcript(transcripts, available_transcripts))
        return TranscriptOptions(video_id, available_transcripts, selected_transcript, tuple(debug_messages))
    except (NoTranscriptFound, TranscriptsDisabled) as exc:
        debug_messages.append(_format_exception(exc))
        return TranscriptOptions(video_id, (), None, tuple(debug_messages))
    except Exception as exc:
        debug_messages.append(_format_exception(exc))
        return TranscriptOptions(video_id, (), None, tuple(debug_messages))


def fetch_transcript_result(video_id: str, translate_to: str | None = None) -> TranscriptResult:
    debug_messages = _build_proxy_debug_messages(video_id)
    try:
        transcript_list = _youtube_transcript_api().list(video_id)
        transcripts = tuple(transcript_list)
        available_transcripts = tuple(_metadata_from_transcript(item) for item in transcripts)
        transcript_source = _select_transcript(transcripts, available_transcripts)

        requested_translation = None
        if translate_to:
            if transcript_source.is_translatable:
                transcript_source = transcript_source.translate(translate_to)
                requested_translation = translate_to
            else:
                debug_messages.append(
                    f"Transcript is not translatable; using original {transcript_source.language_code} transcript."
                )

        transcript_items = tuple(transcript_source.fetch())
    except (NoTranscriptFound, TranscriptsDisabled) as exc:
        debug_messages.append(_format_exception(exc))
        raise TranscriptError(
            "No public transcript or captions were found for this video.",
            tuple(debug_messages),
        ) from exc
    except (IpBlocked, RequestBlocked) as exc:
        debug_messages.append(_format_exception(exc))
        raise TranscriptError(
            "YouTube appears to be temporarily blocking transcript requests from this IP. "
            "Try again later, load a cached transcript, paste the transcript manually, "
            "or use audio transcription fallback if appropriate.",
            tuple(debug_messages),
        ) from exc
    except Exception as exc:
        debug_messages.append(_format_exception(exc))
        raise TranscriptError(f"Transcript extraction failed: {exc}", tuple(debug_messages)) from exc

    transcript_items = _sort_transcript_items(transcript_items)
    start_seconds, end_seconds = _transcript_time_range(transcript_items)
    debug_messages.append(
        "Transcript fetch stats: "
        f"{len(transcript_items)} items, start={_format_seconds(start_seconds)}, end={_format_seconds(end_seconds)}."
    )

    transcript = "\n".join(text for text in (_item_text(item) for item in transcript_items) if text)
    if not transcript:
        raise TranscriptError("Transcript extraction returned no readable text.")

    return TranscriptResult(
        text=transcript,
        video_id=video_id,
        available_transcripts=available_transcripts,
        selected_transcript=_metadata_from_transcript(transcript_source),
        requested_translation=requested_translation,
        item_count=len(transcript_items),
        start_seconds=start_seconds,
        end_seconds=end_seconds,
        debug_messages=tuple(debug_messages),
    )


def fetch_transcript(video_id: str) -> str:
    return fetch_transcript_result(video_id).text


def transcribe_youtube_audio_result(video_id: str) -> TranscriptResult:
    debug_messages = _build_proxy_debug_messages(video_id)
    return _fetch_transcript_result_from_audio(video_id, debug_messages)


def format_debug_exception(exc: Exception) -> str:
    return _format_exception(exc)


def _fetch_transcript_items(video_id: str):
    if hasattr(YouTubeTranscriptApi, "get_transcript"):
        return YouTubeTranscriptApi.get_transcript(video_id)
    return YouTubeTranscriptApi().fetch(video_id)


@contextmanager
def _without_proxy_environment():
    proxy_keys = [key for key in os.environ if "proxy" in key.lower()]
    original = {key: os.environ.get(key) for key in proxy_keys}
    temp_original = {key: os.environ.get(key) for key in ("TMP", "TEMP", "TMPDIR")}
    try:
        for key in proxy_keys:
            os.environ.pop(key, None)
        YTDLP_TRANSCRIPT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        temp_dir = str(YTDLP_TRANSCRIPT_CACHE_DIR.resolve())
        os.environ["TMP"] = temp_dir
        os.environ["TEMP"] = temp_dir
        os.environ["TMPDIR"] = temp_dir
        yield
    finally:
        for key in proxy_keys:
            value = original.get(key)
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        for key, value in temp_original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _parse_ytdlp_json3(path: Path) -> tuple[dict, ...]:
    data = json.loads(path.read_text(encoding="utf-8"))
    items = []
    for event in data.get("events", []):
        segments = event.get("segs") or []
        text = "".join(str(segment.get("utf8", "")) for segment in segments).strip()
        if not text:
            continue
        start_ms = event.get("tStartMs")
        duration_ms = event.get("dDurationMs", 0)
        try:
            start = float(start_ms) / 1000 if start_ms is not None else None
        except (TypeError, ValueError):
            start = None
        try:
            duration = float(duration_ms or 0) / 1000
        except (TypeError, ValueError):
            duration = 0.0
        items.append({"text": text, "start": start, "duration": duration})
    return tuple(items)


def _metadata_from_ytdlp_path(path: Path) -> TranscriptMetadata:
    language_code = "unknown"
    parts = path.name.split(".")
    if len(parts) >= 3:
        language_code = parts[-2]
    return TranscriptMetadata(
        language=language_code,
        language_code=language_code,
        is_generated=False,
        is_translatable=False,
    )


def _fetch_transcript_result_from_audio(video_id: str, debug_messages: list[str]) -> TranscriptResult:
    audio_path = _download_audio_with_ytdlp(video_id, debug_messages)
    text = transcribe_audio_file(audio_path, language="zh", debug_messages=debug_messages).strip()
    if not text:
        raise RuntimeError("OpenAI audio transcription returned no readable text.")

    metadata = TranscriptMetadata(
        language="audio transcription",
        language_code="audio-transcription",
        is_generated=True,
        is_translatable=False,
    )
    debug_messages.append(f"Audio transcription fallback loaded {audio_path}")
    return TranscriptResult(
        text=text,
        video_id=video_id,
        available_transcripts=(metadata,),
        selected_transcript=metadata,
        item_count=0,
        source_type="audio_transcription",
        transcript_provider="openai_transcription",
        debug_messages=tuple(debug_messages),
    )


def _download_audio_with_ytdlp(video_id: str, debug_messages: list[str]) -> Path:
    try:
        from yt_dlp import YoutubeDL
    except ImportError as exc:
        raise RuntimeError("yt-dlp audio fallback is not installed.") from exc

    YTDLP_AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    before = set(YTDLP_AUDIO_CACHE_DIR.glob(f"{video_id}.*"))
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "format": "bestaudio[ext=m4a]/bestaudio/best[height<=360]",
        "outtmpl": {"default": f"{video_id}.%(ext)s"},
        "paths": {
            "home": str(YTDLP_AUDIO_CACHE_DIR),
            "temp": str(YTDLP_AUDIO_CACHE_DIR),
        },
        "proxy": "",
        "noprogress": True,
    }
    debug_messages.append("Trying yt-dlp audio fallback.")
    with _without_proxy_environment():
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
    after = set(YTDLP_AUDIO_CACHE_DIR.glob(f"{video_id}.*"))
    downloaded = sorted(after - before)
    if downloaded:
        return downloaded[0]
    existing = sorted(after)
    if existing:
        return existing[0]
    raise RuntimeError("yt-dlp audio fallback did not write an audio file.")


def transcribe_audio_file(audio_path: Path, *, language: str = "zh", debug_messages: list[str] | None = None) -> str:
    messages = debug_messages if debug_messages is not None else []
    return _transcribe_audio_with_openai(audio_path, messages, language=language)


def _transcribe_audio_with_openai(audio_path: Path, debug_messages: list[str], *, language: str = "zh") -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set; audio fallback cannot transcribe the downloaded file.")
    debug_messages.append(f"Transcribing audio fallback with {OPENAI_TRANSCRIPTION_MODEL}.")
    request_kwargs = {
        "model": OPENAI_TRANSCRIPTION_MODEL,
        "response_format": "text",
    }
    if language and language != "unknown":
        request_kwargs["language"] = language
    with httpx.Client(trust_env=OPENAI_USE_SYSTEM_PROXY, timeout=600.0) as http_client:
        client = OpenAI(api_key=OPENAI_API_KEY, http_client=http_client)
        with audio_path.open("rb") as audio_file:
            return client.audio.transcriptions.create(
                file=audio_file,
                **request_kwargs,
            )


def _youtube_transcript_api() -> YouTubeTranscriptApi:
    http_client = _youtube_http_client()
    if "http_client" in inspect.signature(YouTubeTranscriptApi).parameters:
        return YouTubeTranscriptApi(http_client=http_client)
    return YouTubeTranscriptApi()


def _youtube_http_client() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    return session


def _build_proxy_debug_messages(video_id: str) -> list[str]:
    proxy_env = {key: value for key, value in os.environ.items() if "proxy" in key.lower()}
    proxy_url = YOUTUBE_PROXY_DEBUG_URL.format(video_id=video_id)
    return [
        f"os.environ proxy variables: {proxy_env}",
        f"requests.utils.get_environ_proxies({proxy_url!r}): {requests.utils.get_environ_proxies(proxy_url)}",
        "YouTube transcript HTTP client trust_env=False: True",
    ]


def _select_transcript(transcripts, available_transcripts: tuple[TranscriptMetadata, ...]):
    if not available_transcripts:
        raise TranscriptError("No public transcript or captions were found for this video.")

    transcripts = tuple(transcripts)

    for language_code in LANGUAGE_PRIORITY:
        for transcript in transcripts:
            if transcript.language_code == language_code and not transcript.is_generated:
                return transcript

    for language_code in LANGUAGE_PRIORITY:
        for transcript in transcripts:
            if transcript.language_code == language_code:
                return transcript

    return transcripts[0]


def _metadata_from_transcript(transcript) -> TranscriptMetadata:
    translation_languages = tuple(
        (item.language_code, item.language) for item in getattr(transcript, "translation_languages", [])
    )
    return TranscriptMetadata(
        language=getattr(transcript, "language", ""),
        language_code=getattr(transcript, "language_code", ""),
        is_generated=bool(getattr(transcript, "is_generated", False)),
        is_translatable=bool(getattr(transcript, "is_translatable", False)),
        translation_languages=translation_languages,
    )


def _item_text(item) -> str:
    if isinstance(item, dict):
        return item.get("text", "").strip()
    return getattr(item, "text", "").strip()


def _item_start(item) -> float | None:
    value = item.get("start") if isinstance(item, dict) else getattr(item, "start", None)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _item_duration(item) -> float:
    value = item.get("duration") if isinstance(item, dict) else getattr(item, "duration", 0)
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _sort_transcript_items(items):
    indexed_items = tuple(enumerate(items))
    return tuple(
        item
        for _, item in sorted(
            indexed_items,
            key=lambda indexed_item: (
                _item_start(indexed_item[1]) is None,
                _item_start(indexed_item[1]) or 0,
                indexed_item[0],
            ),
        )
    )


def _transcript_time_range(items) -> tuple[float | None, float | None]:
    starts = tuple(start for start in (_item_start(item) for item in items) if start is not None)
    if not starts:
        return None, None

    first_start = min(starts)
    last_end = max(
        (start + _item_duration(item))
        for item in items
        for start in [_item_start(item)]
        if start is not None
    )
    return first_start, last_end


def _format_seconds(value: float | None) -> str:
    if value is None:
        return "unknown"
    minutes, seconds = divmod(int(value), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def _format_exception(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"
