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
