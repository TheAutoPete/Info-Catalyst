import inspect
import os
from dataclasses import dataclass, field

import requests

from youtube_transcript_api import NoTranscriptFound, TranscriptsDisabled, YouTubeTranscriptApi


class TranscriptError(RuntimeError):
    def __init__(self, message: str, debug_messages: tuple[str, ...] = ()):
        super().__init__(message)
        self.debug_messages = debug_messages


LANGUAGE_PRIORITY = ("zh-TW", "zh-Hant", "zh-Hans", "zh-CN", "zh", "en")
TRANSLATION_TARGETS = {
    "en": "English",
}
YOUTUBE_PROXY_DEBUG_URL = "https://www.youtube.com/watch?v={video_id}"


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

        transcript_items = transcript_source.fetch()
    except (NoTranscriptFound, TranscriptsDisabled) as exc:
        debug_messages.append(_format_exception(exc))
        raise TranscriptError(
            "No public transcript or captions were found for this video.",
            tuple(debug_messages),
        ) from exc
    except Exception as exc:
        debug_messages.append(_format_exception(exc))
        raise TranscriptError(f"Transcript extraction failed: {exc}", tuple(debug_messages)) from exc

    transcript = "\n".join(text for text in (_item_text(item) for item in transcript_items) if text)
    if not transcript:
        raise TranscriptError("Transcript extraction returned no readable text.")

    return TranscriptResult(
        text=transcript,
        video_id=video_id,
        available_transcripts=available_transcripts,
        selected_transcript=_metadata_from_transcript(transcript_source),
        requested_translation=requested_translation,
        debug_messages=tuple(debug_messages),
    )


def fetch_transcript(video_id: str) -> str:
    return fetch_transcript_result(video_id).text


def format_debug_exception(exc: Exception) -> str:
    return _format_exception(exc)


def _fetch_transcript_items(video_id: str):
    if hasattr(YouTubeTranscriptApi, "get_transcript"):
        return YouTubeTranscriptApi.get_transcript(video_id)
    return YouTubeTranscriptApi().fetch(video_id)


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


def _format_exception(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"
