import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


GENERIC_REPORT_TITLES = {
    "report",
    "summary",
    "summary report",
    "deep analysis report",
    "investment lens report",
    "bias check report",
    "titan input report",
    "quick summary report",
    "untitled",
    "untitled report",
    "untitled video",
}

WINDOWS_INVALID_FILENAME_CHARS = '<>:"/\\|?*'
MAX_FILENAME_LENGTH = 180
MAX_FILENAME_PART_LENGTH = 72
TITLE_BACKFILL_FIELDS = ("report_title", "display_title", "title_source", "title_generated_at")


def extract_report_title(markdown_text: str) -> str:
    for line in (markdown_text or "").splitlines():
        match = re.match(r"^\s{0,3}#\s+(.+?)\s*$", line)
        if not match:
            continue
        title = _clean_title(match.group(1))
        if title and not is_generic_report_title(title):
            return title
        return ""
    return ""


def is_generic_report_title(title: str) -> bool:
    normalized = _normalize_title(title)
    if not normalized:
        return True
    return normalized in GENERIC_REPORT_TITLES


def build_display_title(
    *,
    report_title: str,
    generated_at: datetime | str | None = None,
    analysis_mode: str = "",
) -> str:
    title = _clean_title(report_title) or "Untitled report"
    timestamp = _format_display_timestamp(generated_at)
    parts = [part for part in (timestamp, title, _clean_title(analysis_mode)) if part]
    return " - ".join(parts)


def sanitize_report_filename_part(value: str) -> str:
    cleaned = _clean_title(value)
    translation = str.maketrans({char: "-" for char in WINDOWS_INVALID_FILENAME_CHARS})
    cleaned = cleaned.translate(translation)
    cleaned = re.sub(r"\s+", "-", cleaned, flags=re.UNICODE)
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip(" .-_")
    cleaned = re.sub(r"[^\w.\-]+", "-", cleaned, flags=re.UNICODE)
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip(" .-_")
    return cleaned[:MAX_FILENAME_PART_LENGTH] or "report"


def build_safe_report_filename(
    *,
    generated_at: datetime,
    analysis_mode: str,
    report_title: str,
    source_id: str = "",
    suffix: str = ".md",
) -> str:
    timestamp = generated_at.strftime("%Y-%m-%d_%H%M")
    mode_part = sanitize_report_filename_part(analysis_mode or "report").lower()
    title_part = sanitize_report_filename_part(report_title or "report").lower()
    source_part = sanitize_report_filename_part(source_id) if source_id else ""
    stem_parts = [timestamp, mode_part, title_part]
    if source_part:
        stem_parts.append(source_part)
    stem = "_".join(stem_parts)
    max_stem_length = MAX_FILENAME_LENGTH - len(suffix)
    if len(stem) > max_stem_length:
        overflow = len(stem) - max_stem_length
        title_part = title_part[: max(16, len(title_part) - overflow)].rstrip(" .-_") or "report"
        stem_parts = [timestamp, mode_part, title_part]
        if source_part:
            stem_parts.append(source_part)
        stem = "_".join(stem_parts)[:max_stem_length].rstrip(" .-_")
    return f"{stem}{suffix}"


def resolve_report_title(
    *,
    markdown_text: str = "",
    user_input_title: str = "",
    source_title: str = "",
    video_title: str = "",
    video_id: str = "",
    file_stem: str = "",
    analysis_mode: str = "",
    generated_at: datetime | str | None = None,
) -> dict[str, str]:
    report_title = extract_report_title(markdown_text)
    title_source = "report_h1" if report_title else ""

    if not report_title:
        candidates: list[tuple[str, str]] = [
            ("user_input", user_input_title),
            ("source_title", source_title),
            ("video_title", video_title),
            ("fallback", video_id),
            ("fallback", _title_from_file_stem(file_stem)),
        ]
        for source, value in candidates:
            candidate = _clean_title(value)
            if candidate and not is_generic_report_title(candidate):
                report_title = candidate
                title_source = source
                break

    if not report_title:
        report_title = "Untitled report"
        title_source = "fallback"

    resolved_source_title = _clean_title(source_title or video_title or user_input_title)
    timestamp = _format_iso_timestamp(generated_at)
    return {
        "source_title": resolved_source_title,
        "report_title": report_title,
        "display_title": build_display_title(
            report_title=report_title,
            generated_at=generated_at,
            analysis_mode=analysis_mode,
        ),
        "title_source": title_source,
        "title_generated_at": timestamp,
    }


def resolve_display_title_from_metadata(
    metadata: dict[str, Any],
    *,
    markdown_text: str = "",
    file_stem: str = "",
) -> str:
    explicit = str(metadata.get("display_title") or "").strip()
    if explicit:
        return explicit

    report_title = str(metadata.get("report_title") or "").strip()
    if report_title:
        return build_display_title(
            report_title=report_title,
            generated_at=str(metadata.get("generated_at") or ""),
            analysis_mode=str(metadata.get("analysis_mode") or metadata.get("report_type") or ""),
        )

    resolved = resolve_report_title(
        markdown_text=markdown_text,
        source_title=str(metadata.get("source_title") or ""),
        video_title=str(metadata.get("video_title") or ""),
        video_id=str(metadata.get("video_id") or ""),
        file_stem=file_stem,
        analysis_mode=str(metadata.get("analysis_mode") or metadata.get("report_type") or ""),
        generated_at=str(metadata.get("generated_at") or ""),
    )
    return resolved["display_title"]


def needs_title_backfill(metadata: dict[str, Any]) -> bool:
    if not isinstance(metadata, dict):
        return True
    return any(not _has_text(metadata.get(field)) for field in TITLE_BACKFILL_FIELDS)


def build_title_backfill_payload(
    metadata: dict[str, Any],
    markdown_text: str = "",
    file_stem: str = "",
) -> dict[str, str]:
    metadata = metadata or {}
    existing_report_title = _clean_title(str(metadata.get("report_title") or ""))
    report_title = extract_report_title(markdown_text)
    title_source = "report_h1" if report_title else ""

    if not report_title and existing_report_title and not is_generic_report_title(existing_report_title):
        report_title = existing_report_title
        title_source = "existing_report_title"

    if not report_title:
        candidates: list[tuple[str, str]] = [
            ("video_title", str(metadata.get("video_title") or "")),
            ("source_title", str(metadata.get("source_title") or "")),
            ("fallback", str(metadata.get("video_id") or "")),
            ("fallback", _title_from_file_stem(file_stem)),
        ]
        for source, value in candidates:
            candidate = _clean_title(value)
            if candidate and not is_generic_report_title(candidate):
                report_title = candidate
                title_source = source
                break

    if not report_title:
        report_title = "Untitled report"
        title_source = "fallback"

    generated_at = str(metadata.get("generated_at") or "")
    payload = {
        "report_title": report_title,
        "display_title": build_display_title(
            report_title=report_title,
            generated_at=generated_at,
            analysis_mode=str(metadata.get("analysis_mode") or metadata.get("report_type") or ""),
        ),
        "title_source": title_source,
        "title_generated_at": _format_iso_timestamp(generated_at),
    }

    preserved: dict[str, str] = {}
    for field in TITLE_BACKFILL_FIELDS:
        current = str(metadata.get(field) or "").strip()
        if not current:
            continue
        if field == "report_title" and is_generic_report_title(current):
            continue
        preserved[field] = current
    return {**payload, **preserved}


def preview_title_backfill(metadata_path: Path, report_path: Path) -> dict[str, Any]:
    metadata = _read_json_metadata(metadata_path)
    needed = needs_title_backfill(metadata)
    markdown_text = _read_markdown_if_needed(report_path, needed)
    payload = build_title_backfill_payload(metadata, markdown_text=markdown_text, file_stem=report_path.stem)
    current_display_title = resolve_display_title_from_metadata(
        metadata,
        markdown_text=markdown_text,
        file_stem=report_path.stem,
    )
    updates = {field: value for field, value in payload.items() if str(metadata.get(field) or "").strip() != value}
    return {
        "metadata_path": metadata_path,
        "report_path": report_path,
        "needs_backfill": needed,
        "current_display_title": current_display_title,
        "proposed": payload,
        "updates": updates if needed else {},
        "missing_report": not report_path.exists(),
    }


def backfill_title_metadata(metadata_path: Path, report_path: Path) -> dict[str, Any]:
    preview = preview_title_backfill(metadata_path, report_path)
    if not preview["needs_backfill"]:
        return {**preview, "updated": False, "skipped": True}

    metadata = _read_json_metadata(metadata_path)
    if not metadata:
        return {**preview, "updated": False, "skipped": True}

    updated_metadata = dict(metadata)
    for field in TITLE_BACKFILL_FIELDS:
        proposed = str(preview["proposed"].get(field) or "").strip()
        current = str(updated_metadata.get(field) or "").strip()
        if field == "report_title" and current and not is_generic_report_title(current):
            continue
        if current and field != "report_title":
            continue
        updated_metadata[field] = proposed

    metadata_path.write_text(json.dumps(updated_metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {**preview, "updated": True, "skipped": False, "metadata": updated_metadata}


def _clean_title(value: str) -> str:
    value = re.sub(r"^#+\s*", "", str(value or "").strip())
    value = re.sub(r"[*_`]+", "", value)
    value = re.sub(r"\s+", " ", value).strip(" \t\r\n-")
    return value


def _normalize_title(title: str) -> str:
    cleaned = _clean_title(title).casefold()
    cleaned = re.sub(r"[\W_]+", " ", cleaned, flags=re.UNICODE)
    return re.sub(r"\s+", " ", cleaned).strip()


def _format_display_timestamp(value: datetime | str | None) -> str:
    parsed = _parse_datetime(value)
    if parsed:
        return parsed.strftime("%Y-%m-%d %H:%M")
    return ""


def _format_iso_timestamp(value: datetime | str | None) -> str:
    parsed = _parse_datetime(value)
    if parsed:
        return parsed.isoformat(timespec="seconds")
    return datetime.now().isoformat(timespec="seconds")


def _parse_datetime(value: datetime | str | None) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _title_from_file_stem(file_stem: str) -> str:
    stem = Path(file_stem or "").stem
    stem = re.sub(r"^\d{4}-\d{2}-\d{2}_\d{4}[_-]?", "", stem)
    stem = re.sub(r"^\d{8}-\d{6}[_-]?", "", stem)
    stem = stem.replace("_", " ").replace("-", " ")
    return _clean_title(stem)


def _has_text(value: Any) -> bool:
    return bool(str(value or "").strip())


def _read_json_metadata(path: Path) -> dict[str, Any]:
    try:
        if path and path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError, TypeError):
        return {}
    return {}


def _read_markdown_if_needed(path: Path, needed: bool) -> str:
    if not needed:
        return ""
    try:
        if path and path.exists():
            return path.read_text(encoding="utf-8")
    except OSError:
        return ""
    return ""
