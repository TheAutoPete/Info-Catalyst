import re
import importlib
from datetime import datetime
from pathlib import Path

from config import REPORTS_DIR
from services import report_archive as _report_archive


report_archive = importlib.reload(_report_archive)


def save_report(report_type: str, content: str, source_label: str, reports_dir: Path = REPORTS_DIR) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"{timestamp}-{_slugify(source_label)}-{_slugify(report_type)}.md"
    path = reports_dir / filename
    path.write_text(content.strip() + "\n", encoding="utf-8")
    return path


def save_report_with_metadata(
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
    usage: list[dict] | None = None,
    transcript_source: str = "",
    transcript_provider: str = "",
    transcript_cache_path: str = "",
    transcript_created_at: str = "",
    output_language: str = "",
    output_language_label: str = "",
) -> Path:
    record = report_archive.save_archived_report(
        report_type,
        content,
        video_id=video_id,
        source_url=source_url,
        video_title=video_title,
        source_type=source_type,
        source_id=source_id,
        source_title=source_title,
        transcript_language=transcript_language,
        models=models,
        analysis_mode=analysis_mode,
        selected_model=selected_model,
        reasoning_effort=reasoning_effort,
        model_override=model_override,
        usage=usage,
        transcript_source=transcript_source,
        transcript_provider=transcript_provider,
        transcript_cache_path=transcript_cache_path,
        transcript_created_at=transcript_created_at,
        output_language=output_language,
        output_language_label=output_language_label,
    )
    return record.report_path


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-").lower()
    return slug[:80] or "report"
