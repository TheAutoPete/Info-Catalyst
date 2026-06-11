import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import config


TRANSCRIPTS_DIR = getattr(
    config,
    "TRANSCRIPTS_DIR",
    getattr(config, "BASE_DIR", Path(__file__).resolve().parents[1]) / "reports" / "transcripts",
)


@dataclass(frozen=True)
class TranscriptCacheRecord:
    source_id: str
    source_type: str
    transcript_text: str
    transcript_provider: str
    source_url: str = ""
    video_id: str = ""
    transcript_language: str = ""
    is_generated: bool = False
    available_transcripts: tuple[dict[str, Any], ...] = ()
    fetched_at: str = ""
    created_at: str = ""
    transcript_cache_path: str = ""


def cache_path_for_youtube(video_id: str, transcripts_dir: Path = TRANSCRIPTS_DIR) -> Path:
    return transcripts_dir / f"{_safe_source_id(video_id)}.json"


def cache_path_for_source(source_id: str, transcripts_dir: Path = TRANSCRIPTS_DIR) -> Path:
    if _is_safe_filename_stem(source_id):
        return transcripts_dir / f"{source_id}.json"
    digest = hashlib.sha256(source_id.encode("utf-8")).hexdigest()[:24]
    return transcripts_dir / f"{digest}.json"


def read_transcript_cache(path: Path) -> TranscriptCacheRecord | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return _record_from_dict(data, path)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


def read_youtube_transcript_cache(video_id: str, transcripts_dir: Path = TRANSCRIPTS_DIR) -> TranscriptCacheRecord | None:
    return read_transcript_cache(cache_path_for_youtube(video_id, transcripts_dir))


def write_transcript_cache(
    *,
    source_id: str,
    source_type: str,
    transcript_text: str,
    transcript_provider: str,
    source_url: str = "",
    video_id: str = "",
    transcript_language: str = "",
    is_generated: bool = False,
    available_transcripts: tuple[dict[str, Any], ...] | list[dict[str, Any]] = (),
    fetched_at: str = "",
    created_at: str = "",
    transcripts_dir: Path = TRANSCRIPTS_DIR,
) -> TranscriptCacheRecord:
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().isoformat(timespec="seconds")
    if not fetched_at and source_type == "youtube":
        fetched_at = timestamp
    if not created_at and source_type != "youtube":
        created_at = timestamp

    path = cache_path_for_youtube(video_id, transcripts_dir) if video_id else cache_path_for_source(source_id, transcripts_dir)
    record = TranscriptCacheRecord(
        source_id=source_id,
        video_id=video_id,
        source_url=source_url,
        source_type=source_type,
        transcript_language=transcript_language,
        transcript_text=transcript_text,
        is_generated=is_generated,
        fetched_at=fetched_at,
        created_at=created_at,
        available_transcripts=tuple(dict(item) for item in available_transcripts),
        transcript_provider=transcript_provider,
        transcript_cache_path=str(path),
    )
    path.write_text(json.dumps(asdict(record), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return record


def _record_from_dict(data: dict[str, Any], path: Path) -> TranscriptCacheRecord:
    return TranscriptCacheRecord(
        source_id=str(data.get("source_id") or data.get("video_id") or ""),
        video_id=str(data.get("video_id") or ""),
        source_url=str(data.get("source_url") or ""),
        source_type=str(data.get("source_type") or "cached"),
        transcript_language=str(data.get("transcript_language") or ""),
        transcript_text=str(data.get("transcript_text") or ""),
        is_generated=bool(data.get("is_generated") or False),
        fetched_at=str(data.get("fetched_at") or ""),
        created_at=str(data.get("created_at") or ""),
        available_transcripts=tuple(dict(item) for item in data.get("available_transcripts") or ()),
        transcript_provider=str(data.get("transcript_provider") or ""),
        transcript_cache_path=str(data.get("transcript_cache_path") or path),
    )


def _safe_source_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", value.strip()).strip("-_")
    return cleaned[:120] or hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def _is_safe_filename_stem(value: str) -> bool:
    return bool(value) and bool(re.fullmatch(r"[A-Za-z0-9_-]{1,120}", value))
