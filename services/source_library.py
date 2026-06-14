from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from config import REPORTS_DIR, REPORT_METADATA_DIR
from services.report_archive import ReportRecord, list_recent_reports, read_metadata


UNKNOWN = "Unknown"
SEARCH_FIELDS = (
    "display_title",
    "report_title",
    "source_title",
    "video_title",
    "source_url",
    "video_id",
    "analysis_mode",
    "output_language",
    "output_language_label",
    "transcript_source",
    "transcript_language",
    "selected_model",
    "source_type",
)


@dataclass(frozen=True)
class SourceLibraryRecord:
    report_path: Path
    metadata_path: Path | None
    display_title: str
    report_title: str
    source_title: str
    video_title: str
    video_id: str
    source_url: str
    analysis_mode: str
    output_language: str
    output_language_label: str
    selected_model: str
    reasoning_effort: str
    transcript_source: str
    transcript_provider: str
    transcript_language: str
    generated_at: str
    context_pack_path: str
    report_type: str
    source_type: str


def load_library_records(
    *,
    reports_dir: Path = REPORTS_DIR,
    metadata_dir: Path = REPORT_METADATA_DIR,
    limit: int = 1000,
) -> list[SourceLibraryRecord]:
    records = list_recent_reports(limit=limit, reports_dir=reports_dir, metadata_dir=metadata_dir)
    return sort_library_records([build_library_record_from_report_record(record) for record in records])


def build_library_record_from_report_record(record: ReportRecord) -> SourceLibraryRecord:
    metadata = read_metadata(record.metadata_path)
    display_title = _first_text(
        metadata.get("display_title"),
        record.display_title,
        record.report_title,
        record.video_title,
        record.source_title,
        record.video_id,
        record.report_path.stem,
        "Untitled report",
    )
    report_title = _first_text(metadata.get("report_title"), record.report_title, display_title)
    source_title = _first_text(metadata.get("source_title"), record.source_title, record.video_title)
    video_title = _first_text(metadata.get("video_title"), record.video_title)
    source_url = _first_text(metadata.get("source_url"), record.source_url)
    video_id = _first_text(metadata.get("video_id"), record.video_id)
    transcript_source = _first_text(metadata.get("transcript_source"), record.transcript_source, UNKNOWN)
    report_type = _first_text(metadata.get("report_type"), record.report_type, UNKNOWN)
    source_type = _first_text(metadata.get("source_type"), record.source_type)

    return SourceLibraryRecord(
        report_path=record.report_path,
        metadata_path=record.metadata_path,
        display_title=display_title,
        report_title=report_title,
        source_title=source_title,
        video_title=video_title,
        video_id=video_id,
        source_url=source_url,
        analysis_mode=_first_text(metadata.get("analysis_mode"), record.analysis_mode, report_type),
        output_language=_first_text(metadata.get("output_language"), record.output_language, UNKNOWN),
        output_language_label=_first_text(metadata.get("output_language_label"), record.output_language_label, UNKNOWN),
        selected_model=_first_text(metadata.get("selected_model"), record.selected_model),
        reasoning_effort=_first_text(metadata.get("reasoning_effort"), record.reasoning_effort),
        transcript_source=transcript_source,
        transcript_provider=_first_text(metadata.get("transcript_provider"), record.transcript_provider),
        transcript_language=_first_text(metadata.get("transcript_language"), record.transcript_language, UNKNOWN),
        generated_at=_first_text(metadata.get("generated_at"), record.generated_at),
        context_pack_path=_first_text(metadata.get("context_pack_path"), record.context_pack_path),
        report_type=report_type,
        source_type=source_type
        or _infer_source_type(
            source_url=source_url,
            video_id=video_id,
            transcript_source=transcript_source,
            report_type=report_type,
        ),
    )


def search_library_records(
    records: list[SourceLibraryRecord],
    query: str,
    *,
    search_report_content: bool = False,
) -> list[SourceLibraryRecord]:
    terms = [term.casefold() for term in str(query or "").split() if term.strip()]
    if not terms:
        return list(records)

    matches = []
    for record in records:
        haystack = " ".join(str(getattr(record, field, "") or "") for field in SEARCH_FIELDS).casefold()
        if search_report_content:
            haystack = f"{haystack} {_read_report_for_search(record.report_path)}".casefold()
        if all(term in haystack for term in terms):
            matches.append(record)
    return matches


def filter_library_records(records: list[SourceLibraryRecord], filters: dict[str, str] | None) -> list[SourceLibraryRecord]:
    normalized_filters = {
        key: _normalize_filter_value(value)
        for key, value in (filters or {}).items()
        if _normalize_filter_value(value)
    }
    if not normalized_filters:
        return list(records)

    filtered = []
    for record in records:
        if all(_filter_record_value(record, key) == expected for key, expected in normalized_filters.items()):
            filtered.append(record)
    return filtered


def sort_library_records(records: list[SourceLibraryRecord]) -> list[SourceLibraryRecord]:
    return sorted(records, key=_sort_key, reverse=True)


def build_filter_options(records: list[SourceLibraryRecord], field: str) -> list[str]:
    values = sorted(
        {
            _display_filter_value(_filter_record_value(record, field))
            for record in records
            if _filter_record_value(record, field)
        },
        key=str.casefold,
    )
    return ["All", *values]


def _filter_record_value(record: SourceLibraryRecord, field: str) -> str:
    value = getattr(record, field, "")
    return _normalize_filter_value(value) or UNKNOWN


def _normalize_filter_value(value: Any) -> str:
    text = str(value or "").strip()
    if not text or text.casefold() == "all":
        return ""
    return UNKNOWN if text.casefold() == UNKNOWN.casefold() else text


def _display_filter_value(value: str) -> str:
    return UNKNOWN if not value or value.casefold() == UNKNOWN.casefold() else value


def _first_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _infer_source_type(*, source_url: str, video_id: str, transcript_source: str, report_type: str) -> str:
    source = transcript_source.casefold()
    url = source_url.casefold()
    if source == "podcast_audio_url":
        return "podcast_audio_url"
    if source == "audio_transcription":
        return "audio"
    if source == "article_url":
        return "article_url"
    if source == "manual_text":
        return "manual_text"
    if source == "manual" or video_id == "manual-transcript":
        return "manual"
    if "youtube.com" in url or "youtu.be" in url or _looks_like_youtube_video_id(video_id):
        return "youtube"
    if "youtube" in report_type.casefold():
        return "youtube"
    return "unknown"


def _looks_like_youtube_video_id(value: str) -> bool:
    return len(value) == 11 and all(char.isalnum() or char in {"_", "-"} for char in value)


def _read_report_for_search(path: Path) -> str:
    try:
        if path.exists() and path.stat().st_size <= 250_000:
            return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    return ""


def _sort_key(record: SourceLibraryRecord) -> tuple[float, str]:
    try:
        timestamp = datetime.fromisoformat(record.generated_at).timestamp()
    except ValueError:
        try:
            timestamp = record.report_path.stat().st_mtime
        except OSError:
            timestamp = 0.0
    return timestamp, record.display_title.casefold()
