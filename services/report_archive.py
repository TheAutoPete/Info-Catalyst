import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from config import REPORTS_DIR, REPORT_METADATA_DIR


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
    analysis_mode: str = ""
    selected_model: str = ""
    reasoning_effort: str = ""
    model_override: bool = False
    context_pack_path: str = ""
    transcript_source: str = ""
    transcript_provider: str = ""
    transcript_cache_path: str = ""
    transcript_created_at: str = ""

    @property
    def display_title(self) -> str:
        title = self.video_title or self.video_id or "Untitled video"
        return f"{title} - {self.report_type}"


def save_archived_report(
    report_type: str,
    content: str,
    *,
    video_id: str,
    source_url: str,
    video_title: str = "",
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
    generated_at: datetime | None = None,
    reports_dir: Path = REPORTS_DIR,
    metadata_dir: Path = REPORT_METADATA_DIR,
) -> ReportRecord:
    reports_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    generated_at = generated_at or datetime.now()
    timestamp = generated_at.strftime("%Y-%m-%d_%H%M")
    title_slug = _slugify(video_title or "youtube-video")
    video_slug = _slugify(video_id or "manual-transcript", lowercase=False)
    report_slug = _slugify(report_type)
    filename = f"{timestamp}_{title_slug}_{video_slug}_{report_slug}.md"
    report_path = _dedupe_path(reports_dir / filename)
    report_path.write_text(content.strip() + "\n", encoding="utf-8")

    metadata_path = report_path.with_suffix(".json")
    metadata_path = metadata_dir / metadata_path.name
    metadata = {
        "video_id": video_id,
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
        "report_file_path": str(report_path),
        "report_type": report_type,
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return ReportRecord(
        report_path=report_path,
        metadata_path=metadata_path,
        report_type=report_type,
        video_id=video_id,
        source_url=source_url,
        video_title=video_title,
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


def _record_from_metadata(metadata_path: Path, metadata: dict[str, Any]) -> ReportRecord:
    report_path = Path(metadata.get("report_file_path", ""))
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
        analysis_mode=str(metadata.get("analysis_mode") or ""),
        selected_model=str(metadata.get("selected_model") or ""),
        reasoning_effort=str(metadata.get("reasoning_effort") or ""),
        model_override=bool(metadata.get("model_override") or False),
        context_pack_path=str(metadata.get("context_pack_path") or ""),
        transcript_source=str(metadata.get("transcript_source") or ""),
        transcript_provider=str(metadata.get("transcript_provider") or ""),
        transcript_cache_path=str(metadata.get("transcript_cache_path") or ""),
        transcript_created_at=str(metadata.get("transcript_created_at") or ""),
    )


def _record_from_legacy_markdown(path: Path) -> ReportRecord:
    return ReportRecord(
        report_path=path,
        metadata_path=None,
        report_type=_infer_report_type(path),
        video_id=_infer_video_id(path),
        source_url="",
        video_title="",
        transcript_language="",
        generated_at=datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
        models={},
        analysis_mode="",
        selected_model="",
        reasoning_effort="",
        model_override=False,
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


def _slugify(value: str, *, lowercase: bool = True) -> str:
    slug = re.sub(r"[^\w-]+", "-", value.strip(), flags=re.UNICODE)
    slug = re.sub(r"-{2,}", "-", slug).strip("-_")
    if lowercase:
        slug = slug.lower()
    return slug[:80] or "report"
