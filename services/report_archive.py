import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from config import REPORTS_DIR, REPORT_METADATA_DIR, REPORT_CONTEXT_DIR
from services.output_languages import get_output_language
from services.report_titles import (
    build_safe_report_filename,
    resolve_display_title_from_metadata,
    resolve_report_title,
)


@dataclass(frozen=True)
class ReportRecord:
    report_path: Path
    metadata_path: Path | None
    report_type: str
    video_id: str
    source_url: str
    video_title: str
    transcript_language: str
    generated_at: str
    models: dict[str, str]
    source_type: str = "youtube"
    source_id: str = ""
    analysis_mode: str = ""
    selected_model: str = ""
    reasoning_effort: str = ""
    model_override: bool = False
    context_pack_path: str = ""
    transcript_source: str = ""
    transcript_provider: str = ""
    transcript_cache_path: str = ""
    transcript_created_at: str = ""
    output_language: str = ""
    output_language_label: str = ""
    source_title: str = ""
    report_title: str = ""
    metadata_display_title: str = ""
    title_source: str = ""
    title_generated_at: str = ""

    @property
    def display_title(self) -> str:
        if self.metadata_display_title:
            return self.metadata_display_title
        resolved = resolve_report_title(
            source_title=self.source_title,
            video_title=self.video_title,
            video_id=self.video_id,
            file_stem=self.report_path.stem,
            analysis_mode=self.analysis_mode or self.report_type,
            generated_at=self.generated_at,
        )
        return resolved["display_title"]


def save_archived_report(
    report_type: str,
    content: str,
    *,
    video_id: str,
    source_url: str,
    video_title: str = "",
    source_type: str = "youtube",
    source_id: str = "",
    source_title: str = "",
    transcript_language: str = "",
    models: dict[str, str] | None = None,
    analysis_mode: str = "",
    selected_model: str = "",
    reasoning_effort: str = "",
    model_override: bool = False,
    usage: list[dict[str, Any]] | None = None,
    context_pack_path: str = "",
    transcript_source: str = "",
    transcript_provider: str = "",
    transcript_cache_path: str = "",
    transcript_created_at: str = "",
    output_language: str = "",
    output_language_label: str = "",
    generated_at: datetime | None = None,
    reports_dir: Path = REPORTS_DIR,
    metadata_dir: Path = REPORT_METADATA_DIR,
) -> ReportRecord:
    reports_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    generated_at = generated_at or datetime.now()
    source_title = source_title or video_title
    source_id = source_id or video_id
    title_metadata = resolve_report_title(
        markdown_text=content,
        source_title=source_title,
        video_title=video_title,
        video_id=video_id,
        analysis_mode=analysis_mode or report_type,
        generated_at=generated_at,
    )
    filename = build_safe_report_filename(
        generated_at=generated_at,
        analysis_mode=analysis_mode or report_type,
        report_title=title_metadata["report_title"],
        source_id=source_id or video_id or "manual-text",
    )
    report_path = _dedupe_path(reports_dir / filename)
    report_path.write_text(content.strip() + "\n", encoding="utf-8")
    language = get_output_language(output_language or output_language_label)

    metadata_path = report_path.with_suffix(".json")
    metadata_path = metadata_dir / metadata_path.name
    metadata = {
        "video_id": video_id,
        "source_type": source_type,
        "source_id": source_id,
        "source_url": source_url,
        "video_title": video_title,
        "transcript_language": transcript_language,
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "models": models or {},
        "analysis_mode": analysis_mode,
        "selected_model": selected_model,
        "reasoning_effort": reasoning_effort,
        "model_override": model_override,
        "usage": usage or [],
        "context_pack_path": context_pack_path,
        "transcript_source": transcript_source,
        "transcript_provider": transcript_provider,
        "transcript_cache_path": transcript_cache_path,
        "transcript_created_at": transcript_created_at,
        "output_language": language.code,
        "output_language_label": output_language_label or language.label,
        "report_file_path": str(report_path),
        "report_type": report_type,
        **title_metadata,
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return ReportRecord(
        report_path=report_path,
        metadata_path=metadata_path,
        report_type=report_type,
        video_id=video_id,
        source_url=source_url,
        video_title=video_title,
        source_type=source_type,
        source_id=source_id,
        transcript_language=transcript_language,
        generated_at=metadata["generated_at"],
        models=metadata["models"],
        analysis_mode=analysis_mode,
        selected_model=selected_model,
        reasoning_effort=reasoning_effort,
        model_override=model_override,
        context_pack_path=context_pack_path,
        transcript_source=transcript_source,
        transcript_provider=transcript_provider,
        transcript_cache_path=transcript_cache_path,
        transcript_created_at=transcript_created_at,
        output_language=language.code,
        output_language_label=output_language_label or language.label,
        source_title=metadata["source_title"],
        report_title=metadata["report_title"],
        metadata_display_title=metadata["display_title"],
        title_source=metadata["title_source"],
        title_generated_at=metadata["title_generated_at"],
    )


def list_recent_reports(
    limit: int = 20,
    reports_dir: Path = REPORTS_DIR,
    metadata_dir: Path = REPORT_METADATA_DIR,
) -> list[ReportRecord]:
    records = _load_metadata_records(metadata_dir)
    known_paths = {record.report_path.resolve() for record in records if record.report_path.exists()}

    if reports_dir.exists():
        for path in reports_dir.glob("*.md"):
            if path.resolve() not in known_paths:
                records.append(_record_from_legacy_markdown(path))

    existing_records = [record for record in records if record.report_path.exists()]
    return sorted(existing_records, key=lambda record: _sort_time(record), reverse=True)[:limit]


def find_reports_by_video_id(
    video_id: str,
    reports_dir: Path = REPORTS_DIR,
    metadata_dir: Path = REPORT_METADATA_DIR,
) -> list[ReportRecord]:
    if not video_id:
        return []
    return [
        record
        for record in list_recent_reports(limit=500, reports_dir=reports_dir, metadata_dir=metadata_dir)
        if record.video_id == video_id
    ]


def read_report(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def find_report_record_by_path(
    report_path: Path,
    reports_dir: Path = REPORTS_DIR,
    metadata_dir: Path = REPORT_METADATA_DIR,
) -> ReportRecord | None:
    try:
        target = report_path.resolve()
    except OSError:
        target = report_path

    for record in list_recent_reports(limit=1000, reports_dir=reports_dir, metadata_dir=metadata_dir):
        try:
            if record.report_path.resolve() == target:
                return record
        except OSError:
            if record.report_path == report_path:
                return record
    return None


def read_metadata(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return {}


def update_metadata(metadata_path: Path | None, **updates: Any) -> dict[str, Any]:
    if not metadata_path:
        return {}
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata = read_metadata(metadata_path)
    metadata.update(updates)
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return metadata


def append_usage_record(metadata_path: Path | None, usage_record: dict[str, Any]) -> dict[str, Any]:
    if not metadata_path:
        return {}
    metadata = read_metadata(metadata_path)
    usage = metadata.get("usage")
    if not isinstance(usage, list):
        usage = []
    usage.append(usage_record)
    metadata["usage"] = usage
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return metadata


def delete_report_record(
    record: Any,
    *,
    delete_context_pack: bool = True,
    reports_dir: Path = REPORTS_DIR,
    metadata_dir: Path = REPORT_METADATA_DIR,
    context_dir: Path = REPORT_CONTEXT_DIR,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "deleted_report_path": "",
        "deleted_metadata_path": "",
        "deleted_context_pack_path": "",
        "skipped_paths": [],
        "errors": [],
    }

    report_path = Path(getattr(record, "report_path", "") or "")
    metadata_path = getattr(record, "metadata_path", None)
    metadata_path = Path(metadata_path) if metadata_path else metadata_dir / f"{report_path.stem}.json"
    context_pack_path = str(getattr(record, "context_pack_path", "") or "")

    _delete_expected_file(
        report_path,
        allowed_dir=reports_dir,
        result_key="deleted_report_path",
        result=result,
        label="Markdown report",
    )
    _delete_expected_file(
        metadata_path,
        allowed_dir=metadata_dir,
        result_key="deleted_metadata_path",
        result=result,
        label="metadata JSON",
    )

    if delete_context_pack and context_pack_path:
        _delete_expected_file(
            Path(context_pack_path),
            allowed_dir=context_dir,
            result_key="deleted_context_pack_path",
            result=result,
            label="Context Pack",
            unsafe_is_error=False,
        )
    elif context_pack_path:
        result["skipped_paths"].append(str(Path(context_pack_path)))

    logging.info(
        "Deleted report archive record: report=%s metadata=%s context_pack=%s skipped=%s errors=%s",
        result["deleted_report_path"],
        result["deleted_metadata_path"],
        result["deleted_context_pack_path"],
        result["skipped_paths"],
        result["errors"],
    )
    return result


def _load_metadata_records(metadata_dir: Path) -> list[ReportRecord]:
    if not metadata_dir.exists():
        return []

    records = []
    for path in metadata_dir.glob("*.json"):
        try:
            metadata = json.loads(path.read_text(encoding="utf-8"))
            records.append(_record_from_metadata(path, metadata))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            continue
    return records


def _delete_expected_file(
    path: Path,
    *,
    allowed_dir: Path,
    result_key: str,
    result: dict[str, Any],
    label: str,
    unsafe_is_error: bool = True,
) -> None:
    if not str(path):
        return
    path_text = str(path)
    if not _is_path_inside(path, allowed_dir):
        result["skipped_paths"].append(path_text)
        if unsafe_is_error:
            result["errors"].append(f"{label} path is outside the expected directory: {path_text}")
        return
    if not path.exists():
        result["skipped_paths"].append(path_text)
        return
    if not path.is_file():
        result["skipped_paths"].append(path_text)
        result["errors"].append(f"{label} path is not a file: {path_text}")
        return
    try:
        path.unlink()
        result[result_key] = path_text
    except OSError as exc:
        result["errors"].append(f"Could not delete {label}: {exc}")


def _is_path_inside(path: Path, directory: Path) -> bool:
    try:
        resolved_path = path.resolve()
        resolved_directory = directory.resolve()
        return resolved_path == resolved_directory or resolved_directory in resolved_path.parents
    except OSError:
        return False


def _record_from_metadata(metadata_path: Path, metadata: dict[str, Any]) -> ReportRecord:
    report_path = Path(metadata.get("report_file_path", ""))
    language = get_output_language(str(metadata.get("output_language") or metadata.get("output_language_label") or ""))
    markdown_text = _read_report_text_if_available(report_path)
    display_title = resolve_display_title_from_metadata(metadata, markdown_text=markdown_text, file_stem=report_path.stem)
    title_metadata = resolve_report_title(
        markdown_text=markdown_text,
        source_title=str(metadata.get("source_title") or ""),
        video_title=str(metadata.get("video_title") or ""),
        video_id=str(metadata.get("video_id") or ""),
        file_stem=report_path.stem,
        analysis_mode=str(metadata.get("analysis_mode") or metadata.get("report_type") or ""),
        generated_at=str(metadata.get("generated_at") or ""),
    )
    return ReportRecord(
        report_path=report_path,
        metadata_path=metadata_path,
        report_type=str(metadata.get("report_type") or _infer_report_type(report_path)),
        video_id=str(metadata.get("video_id") or ""),
        source_url=str(metadata.get("source_url") or ""),
        video_title=str(metadata.get("video_title") or ""),
        transcript_language=str(metadata.get("transcript_language") or ""),
        generated_at=str(metadata.get("generated_at") or ""),
        models=dict(metadata.get("models") or {}),
        source_type=str(metadata.get("source_type") or ""),
        source_id=str(metadata.get("source_id") or metadata.get("video_id") or ""),
        analysis_mode=str(metadata.get("analysis_mode") or ""),
        selected_model=str(metadata.get("selected_model") or ""),
        reasoning_effort=str(metadata.get("reasoning_effort") or ""),
        model_override=bool(metadata.get("model_override") or False),
        context_pack_path=str(metadata.get("context_pack_path") or ""),
        transcript_source=str(metadata.get("transcript_source") or ""),
        transcript_provider=str(metadata.get("transcript_provider") or ""),
        transcript_cache_path=str(metadata.get("transcript_cache_path") or ""),
        transcript_created_at=str(metadata.get("transcript_created_at") or ""),
        output_language=str(metadata.get("output_language") or language.code),
        output_language_label=str(metadata.get("output_language_label") or language.label),
        source_title=str(metadata.get("source_title") or title_metadata["source_title"]),
        report_title=str(metadata.get("report_title") or title_metadata["report_title"]),
        metadata_display_title=display_title,
        title_source=str(metadata.get("title_source") or title_metadata["title_source"]),
        title_generated_at=str(metadata.get("title_generated_at") or title_metadata["title_generated_at"]),
    )


def _record_from_legacy_markdown(path: Path) -> ReportRecord:
    generated_at = datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
    report_type = _infer_report_type(path)
    video_id = _infer_video_id(path)
    title_metadata = resolve_report_title(
        markdown_text=_read_report_text_if_available(path),
        video_id=video_id,
        file_stem=path.stem,
        analysis_mode=report_type,
        generated_at=generated_at,
    )
    return ReportRecord(
        report_path=path,
        metadata_path=None,
        report_type=report_type,
        video_id=video_id,
        source_url="",
        video_title="",
        transcript_language="",
        generated_at=generated_at,
        models={},
        source_type="youtube" if video_id else "",
        source_id=video_id,
        analysis_mode="",
        selected_model="",
        reasoning_effort="",
        model_override=False,
        output_language=get_output_language().code,
        output_language_label=get_output_language().label,
        source_title=title_metadata["source_title"],
        report_title=title_metadata["report_title"],
        metadata_display_title=title_metadata["display_title"],
        title_source=title_metadata["title_source"],
        title_generated_at=title_metadata["title_generated_at"],
    )


def _sort_time(record: ReportRecord) -> float:
    try:
        return datetime.fromisoformat(record.generated_at).timestamp()
    except ValueError:
        return record.report_path.stat().st_mtime


def _infer_report_type(path: Path) -> str:
    name = path.stem.lower()
    if "deep-analysis" in name or "deep_analysis" in name:
        return "deep-analysis"
    if "summary" in name:
        return "summary"
    return "report"


def _infer_video_id(path: Path) -> str:
    for part in reversed(path.stem.split("-")):
        if len(part) == 11 and all(char.isalnum() or char in {"_", "-"} for char in part):
            return part
    return ""


def _dedupe_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(2, 1000):
        candidate = path.with_name(f"{path.stem}-{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not create a unique report filename for {path.name}.")


def _read_report_text_if_available(path: Path) -> str:
    try:
        if path.exists():
            return path.read_text(encoding="utf-8")
    except OSError:
        return ""
    return ""
