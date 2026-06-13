import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from services.report_archive import find_reports_by_video_id, list_recent_reports, save_archived_report


def test_save_archived_report_writes_markdown_and_metadata():
    workspace = _workspace_tmp_dir()
    reports_dir = workspace / "reports" / "markdown"
    metadata_dir = workspace / "reports" / "metadata"

    try:
        record = save_archived_report(
            "summary",
            "# Summary Report\nBody",
            video_id="dQw4w9WgXcQ",
            source_url="https://youtu.be/dQw4w9WgXcQ",
            video_title="Test Video Title",
            transcript_language="zh-TW",
            models={"summary": "gpt-test"},
            analysis_mode="Quick Summary",
            selected_model="gpt-5.4-mini",
            reasoning_effort="low",
            model_override=False,
            usage=[{"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}],
            transcript_source="manual",
            transcript_provider="manual",
            transcript_cache_path="reports/transcripts/dQw4w9WgXcQ.json",
            transcript_created_at="2026-06-10T16:29:00",
            output_language="en",
            output_language_label="English",
            generated_at=datetime(2026, 6, 10, 16, 30),
            reports_dir=reports_dir,
            metadata_dir=metadata_dir,
        )

        assert record.report_path.name == "2026-06-10_1630_test-video-title_dQw4w9WgXcQ_summary.md"
        assert record.report_path.read_text(encoding="utf-8") == "# Summary Report\nBody\n"

        metadata = json.loads(record.metadata_path.read_text(encoding="utf-8"))
        assert metadata["video_id"] == "dQw4w9WgXcQ"
        assert metadata["source_url"] == "https://youtu.be/dQw4w9WgXcQ"
        assert metadata["video_title"] == "Test Video Title"
        assert metadata["transcript_language"] == "zh-TW"
        assert metadata["models"] == {"summary": "gpt-test"}
        assert metadata["analysis_mode"] == "Quick Summary"
        assert metadata["selected_model"] == "gpt-5.4-mini"
        assert metadata["reasoning_effort"] == "low"
        assert metadata["model_override"] is False
        assert metadata["usage"][0]["total_tokens"] == 120
        assert metadata["transcript_source"] == "manual"
        assert metadata["transcript_provider"] == "manual"
        assert metadata["transcript_cache_path"] == "reports/transcripts/dQw4w9WgXcQ.json"
        assert metadata["transcript_created_at"] == "2026-06-10T16:29:00"
        assert metadata["output_language"] == "en"
        assert metadata["output_language_label"] == "English"
        assert metadata["report_file_path"] == str(record.report_path)
        assert record.output_language == "en"
        assert record.output_language_label == "English"
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def test_recent_reports_and_duplicate_lookup_use_metadata():
    workspace = _workspace_tmp_dir()
    reports_dir = workspace / "reports" / "markdown"
    metadata_dir = workspace / "reports" / "metadata"

    try:
        first = save_archived_report(
            "summary",
            "old",
            video_id="abc12345678",
            source_url="https://youtu.be/abc12345678",
            generated_at=datetime(2026, 6, 10, 12, 0),
            reports_dir=reports_dir,
            metadata_dir=metadata_dir,
        )
        latest = save_archived_report(
            "deep-analysis",
            "new",
            video_id="abc12345678",
            source_url="https://youtu.be/abc12345678",
            generated_at=datetime(2026, 6, 10, 12, 1),
            reports_dir=reports_dir,
            metadata_dir=metadata_dir,
        )

        recent = list_recent_reports(reports_dir=reports_dir, metadata_dir=metadata_dir)
        duplicates = find_reports_by_video_id("abc12345678", reports_dir=reports_dir, metadata_dir=metadata_dir)

        assert [record.report_path for record in recent] == [latest.report_path, first.report_path]
        assert [record.report_path for record in duplicates] == [latest.report_path, first.report_path]
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def test_recent_reports_include_legacy_markdown_without_metadata():
    workspace = _workspace_tmp_dir()
    reports_dir = workspace / "reports" / "markdown"
    metadata_dir = workspace / "reports" / "metadata"
    reports_dir.mkdir(parents=True)
    metadata_dir.mkdir(parents=True)
    legacy_path = reports_dir / "20260610-120000-summary-dQw4w9WgXcQ.md"
    legacy_path.write_text("# Legacy\n", encoding="utf-8")

    try:
        recent = list_recent_reports(reports_dir=reports_dir, metadata_dir=metadata_dir)

        assert len(recent) == 1
        assert recent[0].report_path == legacy_path
        assert recent[0].metadata_path is None
        assert recent[0].report_type == "summary"
        assert recent[0].video_id == "dQw4w9WgXcQ"
        assert recent[0].output_language == "zh-TW"
        assert recent[0].output_language_label == "Traditional Chinese"
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def _workspace_tmp_dir() -> Path:
    path = Path("tests") / ".tmp" / f"report-archive-{uuid.uuid4().hex}"
    path.mkdir(parents=True)
    return path
