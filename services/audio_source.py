import hashlib
import ipaddress
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests

from services.transcript_cache import cache_path_for_source, read_transcript_cache, write_transcript_cache
from services.transcript_provider import transcribe_audio_file


AUDIO_CACHE_DIR = Path("reports") / "audio-cache"
MAX_AUDIO_BYTES = 25 * 1024 * 1024
REQUEST_TIMEOUT = (10, 120)
SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".m4a", ".mp4", ".wav", ".aac", ".webm", ".ogg"}
SUPPORTED_AUDIO_CONTENT_TYPES = {
    "audio/mpeg",
    "audio/mp4",
    "audio/x-m4a",
    "audio/wav",
    "audio/x-wav",
    "audio/aac",
    "audio/webm",
    "audio/ogg",
}
OCTET_STREAM_CONTENT_TYPES = {"application/octet-stream", "binary/octet-stream"}
USER_AGENT = "InfoCatalyst/1.0 (+direct-audio-url-transcription)"


@dataclass(frozen=True)
class AudioSourceResult:
    source_id: str
    source_url: str
    source_title: str
    transcript_text: str
    transcript_language: str
    transcript_provider: str
    cache_path: str
    created_at: str
    warnings: list[str]
    debug_messages: list[str]


class AudioSourceError(Exception):
    pass


def build_audio_source_id(url: str) -> str:
    normalized = str(url or "").strip()
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    return f"audio-{digest}"


def is_supported_audio_url(url: str) -> bool:
    try:
        _validate_audio_url(url)
    except AudioSourceError:
        return False
    return True


def load_cached_audio_transcript(source_id: str):
    return read_transcript_cache(cache_path_for_source(source_id))


def download_audio_url(url: str, *, source_id: str) -> Path:
    parsed = _validate_audio_url(url)
    debug_path = AUDIO_CACHE_DIR / f"{source_id}{_audio_extension(parsed.path) or '.audio'}"
    AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    try:
        with requests.get(
            url,
            stream=True,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
            allow_redirects=True,
        ) as response:
            status_code = getattr(response, "status_code", 0)
            if status_code >= 400:
                raise AudioSourceError(f"Audio download failed with HTTP {status_code}.")

            content_type = _normalize_content_type(response.headers.get("Content-Type", ""))
            extension = _audio_extension(parsed.path)
            if not _is_allowed_audio_response(content_type, extension):
                raise AudioSourceError(
                    "That URL did not return a supported audio file. Use a direct MP3, M4A, WAV, AAC, WebM, OGG, or MP4 audio URL."
                )

            content_length = _parse_content_length(response.headers.get("Content-Length"))
            if content_length and content_length > MAX_AUDIO_BYTES:
                raise AudioSourceError(
                    f"Audio file is too large ({content_length:,} bytes). The limit is {MAX_AUDIO_BYTES:,} bytes."
                )

            total = 0
            with debug_path.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 256):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > MAX_AUDIO_BYTES:
                        raise AudioSourceError(
                            f"Audio file is too large. The limit is {MAX_AUDIO_BYTES:,} bytes."
                        )
                    handle.write(chunk)
    except AudioSourceError:
        _delete_file(debug_path)
        raise
    except requests.Timeout as exc:
        _delete_file(debug_path)
        raise AudioSourceError("Audio download timed out. Try a smaller direct audio file URL.") from exc
    except requests.RequestException as exc:
        _delete_file(debug_path)
        raise AudioSourceError(f"Audio download failed: {exc}") from exc
    except OSError as exc:
        _delete_file(debug_path)
        raise AudioSourceError(f"Could not save downloaded audio: {exc}") from exc

    if not debug_path.exists() or debug_path.stat().st_size == 0:
        _delete_file(debug_path)
        raise AudioSourceError("Audio download returned an empty file.")

    return debug_path


def transcribe_audio_url(url: str, *, source_title: str = "", language_hint: str = "") -> AudioSourceResult:
    source_url = str(url or "").strip()
    source_id = build_audio_source_id(source_url)
    warnings = [
        "Audio transcription may take longer and use additional OpenAI API cost.",
        "Only process audio you have the right to process.",
    ]
    debug_messages = [f"Audio source id: {source_id}"]
    audio_path = download_audio_url(source_url, source_id=source_id)
    debug_messages.append(f"Downloaded audio to {audio_path}")

    try:
        transcript_text = transcribe_audio_file(
            audio_path,
            language="" if language_hint == "unknown" else language_hint,
            debug_messages=debug_messages,
        ).strip()
    except Exception as exc:
        raise AudioSourceError(f"Audio transcription failed: {exc}") from exc
    finally:
        _delete_file(audio_path)

    if not transcript_text:
        raise AudioSourceError("Audio transcription returned no readable text.")

    created_at = datetime.now().isoformat(timespec="seconds")
    transcript_language = language_hint or "audio-transcription"
    cache_record = write_transcript_cache(
        source_id=source_id,
        source_type="podcast_audio_url",
        source_url=source_url,
        video_id="",
        transcript_text=transcript_text,
        transcript_language=transcript_language,
        transcript_provider="openai_transcription",
        is_generated=True,
        created_at=created_at,
    )
    debug_messages.append(f"Saved transcript cache: {cache_record.transcript_cache_path}")
    return AudioSourceResult(
        source_id=source_id,
        source_url=source_url,
        source_title=source_title.strip(),
        transcript_text=transcript_text,
        transcript_language=transcript_language,
        transcript_provider="openai_transcription",
        cache_path=cache_record.transcript_cache_path,
        created_at=cache_record.created_at,
        warnings=warnings,
        debug_messages=debug_messages,
    )


def _validate_audio_url(url: str):
    text = str(url or "").strip()
    if not text:
        raise AudioSourceError("Enter a direct audio file URL.")
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"}:
        raise AudioSourceError("Only http:// and https:// direct audio URLs are supported.")
    if not parsed.netloc:
        raise AudioSourceError("Enter a valid direct audio file URL.")
    hostname = (parsed.hostname or "").strip().casefold()
    if _is_blocked_host(hostname):
        raise AudioSourceError("Localhost and private network audio URLs are blocked for safety.")
    if not _audio_extension(parsed.path):
        raise AudioSourceError(
            "Direct audio URL is required. Use an MP3, M4A, WAV, AAC, WebM, OGG, or MP4 audio file URL, or use Manual Text / Article Paste."
        )
    return parsed


def _is_blocked_host(hostname: str) -> bool:
    if not hostname:
        return True
    if hostname == "localhost" or hostname.endswith(".localhost"):
        return True
    try:
        ip = ipaddress.ip_address(hostname.strip("[]"))
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified


def _audio_extension(path: str) -> str:
    suffix = Path(urlparse(path).path).suffix.casefold()
    return suffix if suffix in SUPPORTED_AUDIO_EXTENSIONS else ""


def _normalize_content_type(value: str) -> str:
    return str(value or "").split(";", 1)[0].strip().casefold()


def _is_allowed_audio_response(content_type: str, extension: str) -> bool:
    if content_type in SUPPORTED_AUDIO_CONTENT_TYPES:
        return True
    if content_type in OCTET_STREAM_CONTENT_TYPES and extension:
        return True
    return False


def _parse_content_length(value: str | None) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _delete_file(path: Path) -> None:
    try:
        if path.exists() and path.is_file():
            path.unlink()
    except OSError:
        pass
