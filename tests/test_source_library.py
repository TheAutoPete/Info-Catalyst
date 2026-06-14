import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path

import pytest

from services.report_archive import save_archived_report
from services.source_library import (
    build_library_record_from_report_record,
    filter_library_records,
    load_library_records,
    search_library_records,
)


@pytest.fixture
def workspace():
    path = Path("tests") / ".tmp" / f"source-library-{uuid.uuid4().hex}"
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_load_library_records_from_sample_metadata(workspace):
    reports_dir = workspace / "reports" / "markdown"
    metadata_dir = workspace / "reports" / "metadata"
    saved = _save_report(
        reports_dir=reports_dir,
        metadata_dir=metadata_dir,
        content="# AI Datacenter Power Bottleneck\nBody",
        video_id="abc12345678",
        source_url="https://youtu.be/abc12345678",
        analysis_mode="Deep Analysis",
        output_language="en",
        output_language_label="English",
        transcript_source="youtube",
    )

    records = load_library_records(reports_dir=reports_dir, metadata_dir=metadata_dir)

    assert len(records) == 1
    assert records[0].report_path == saved.report_path
    assert records[0].metadata_path == saved.metadata_path
    assert records[0].display_title == "2026-06-10 12:00 - AI Datacenter Power Bottleneck - Deep Analysis"
    assert records[0].source_type == "youtube"


def test_build_library_record_prefers_clean_display_title(workspace):
    reports_dir = workspace / "reports" / "markdown"
    metadata_dir = workspace / "reports" / "metadata"
    saved = _save_report(reports_dir=reports_dir, metadata_dir=metadata_dir)
    metadata = json.loads(saved.metadata_path.read_text(encoding="utf-8"))
    metadata["display_title"] = "Pinned Clean Title"
    saved.metadata_path.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")

    record = build_library_record_from_report_record(saved)

    assert record.display_title == "Pinned Clean Title"


def test_library_record_falls_back_when_display_title_is_missing(workspace):
    reports_dir = workspace / "reports" / "markdown"
    metadata_dir = workspace / "reports" / "metadata"
    reports_dir.mkdir(parents=True)
    metadata_dir.mkdir(parents=True)
    report_path = reports_dir / "legacy.md"
    metadata_path = metadata_dir / "legacy.json"
    report_path.write_text("# Legacy H1\nBody\n", encoding="utf-8")
    metadata_path.write_text(
        json.dumps(
            {
                "video_id": "abc12345678",
                "video_title": "Legacy Video",
                "generated_at": "2026-06-10T12:00:00",
                "analysis_mode": "Quick Summary",
                "report_file_path": str(report_path),
                "report_type": "summary",
            }
        ),
        encoding="utf-8",
    )

    records = load_library_records(reports_dir=reports_dir, metadata_dir=metadata_dir)

    assert records[0].display_title == "2026-06-10 12:00 - Legacy H1 - Quick Summary"
    assert records[0].report_title == "Legacy H1"


def test_search_by_report_title(workspace):
    records = _library_records(workspace)

    matches = search_library_records(records, "Power Bottleneck")

    assert [record.video_id for record in matches] == ["abc12345678"]


def test_search_by_display_title(workspace):
    records = _library_records(workspace)

    matches = search_library_records(records, "Pinned Source")

    assert [record.video_id for record in matches] == ["def12345678"]


def test_search_by_video_id(workspace):
    records = _library_records(workspace)

    matches = search_library_records(records, "def12345678")

    assert [record.video_id for record in matches] == ["def12345678"]


def test_search_by_source_url(workspace):
    records = _library_records(workspace)

    matches = search_library_records(records, "channel-update")

    assert [record.video_id for record in matches] == ["def12345678"]


def test_search_by_analysis_mode(workspace):
    records = _library_records(workspace)

    matches = search_library_records(records, "Investment Lens")

    assert [record.video_id for record in matches] == ["def12345678"]


def test_filter_by_analysis_mode(workspace):
    records = _library_records(workspace)

    matches = filter_library_records(records, {"analysis_mode": "Quick Summary"})

    assert [record.video_id for record in matches] == ["abc12345678"]


def test_filter_by_output_language(workspace):
    records = _library_records(workspace)

    matches = filter_library_records(records, {"output_language_label": "Japanese"})

    assert [record.video_id for record in matches] == ["def12345678"]


def test_filter_by_transcript_source(workspace):
    records = _library_records(workspace)

    matches = filter_library_records(records, {"transcript_source": "manual"})

    assert [record.video_id for record in matches] == ["abc12345678"]


def test_filter_by_source_type(workspace):
    records = _library_records(workspace)

    matches = filter_library_records(records, {"source_type": "youtube"})

    assert [record.video_id for record in matches] == ["def12345678"]


def test_handle_legacy_metadata_with_missing_fields(workspace):
    reports_dir = workspace / "reports" / "markdown"
    metadata_dir = workspace / "reports" / "metadata"
    reports_dir.mkdir(parents=True)
    metadata_dir.mkdir(parents=True)
    report_path = reports_dir / "minimal.md"
    report_path.write_text("Body only\n", encoding="utf-8")
    (metadata_dir / "minimal.json").write_text(
        json.dumps({"report_file_path": str(report_path), "generated_at": "2026-06-10T12:00:00"}),
        encoding="utf-8",
    )

    records = load_library_records(reports_dir=reports_dir, metadata_dir=metadata_dir)

    assert records[0].display_title == "2026-06-10 12:00 - minimal"
    assert records[0].transcript_source == "Unknown"
    assert records[0].source_type == "unknown"


def test_empty_query_returns_all_records(workspace):
    records = _library_records(workspace)

    matches = search_library_records(records, "")

    assert matches == records


def test_search_and_filter_do_not_call_real_youtube_or_openai(workspace, monkeypatch):
    records = _library_records(workspace)

    def fail(*args, **kwargs):
        raise AssertionError("external API should not be called")

    monkeypatch.setattr("services.openai_client.generate_markdown_with_usage", fail)
    monkeypatch.setattr("services.transcript_provider.fetch_transcript_result", fail)

    matches = filter_library_records(search_library_records(records, "Quick"), {"transcript_source": "manual"})

    assert [record.video_id for record in matches] == ["abc12345678"]


def _library_records(workspace):
    reports_dir = workspace / "reports" / "markdown"
    metadata_dir = workspace / "reports" / "metadata"
    first = _save_report(
        reports_dir=reports_dir,
        metadata_dir=metadata_dir,
        content="# AI Datacenter Power Bottleneck\nBody",
        video_id="abc12345678",
        source_url="https://youtu.be/abc12345678",
        analysis_mode="Quick Summary",
        output_language="en",
        output_language_label="English",
        transcript_source="manual",
        generated_at=datetime(2026, 6, 10, 12, 0),
    )
    second = _save_report(
        reports_dir=reports_dir,
        metadata_dir=metadata_dir,
        content="# Semiconductor Channel Update\nBody",
        video_id="def12345678",
        source_url="https://youtube.com/watch?v=def12345678&topic=channel-update",
        analysis_mode="Investment Lens",
        output_language="ja",
        output_language_label="Japanese",
        transcript_source="youtube",
        generated_at=datetime(2026, 6, 10, 13, 0),
    )
    metadata = json.loads(second.metadata_path.read_text(encoding="utf-8"))
    metadata["display_title"] = "Pinned Source Library Title"
    second.metadata_path.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")

    records = load_library_records(reports_dir=reports_dir, metadata_dir=metadata_dir)
    assert [record.video_id for record in records] == [second.video_id, first.video_id]
    return records


def _save_report(
    *,
    reports_dir,
    metadata_dir,
    content="# AI Datacenter Power Bottleneck\nBody",
    video_id="abc12345678",
    source_url="https://youtu.be/abc12345678",
    analysis_mode="Quick Summary",
    output_language="en",
    output_language_label="English",
    transcript_source="manual",
    generated_at=datetime(2026, 6, 10, 12, 0),
):
    return save_archived_report(
        "summary",
        content,
        video_id=video_id,
        source_url=source_url,
        video_title="Sample Video",
        transcript_language="zh-TW",
        analysis_mode=analysis_mode,
        selected_model="gpt-5.4-mini",
        reasoning_effort="low",
        transcript_source=transcript_source,
        transcript_provider=transcript_source,
        output_language=output_language,
        output_language_label=output_language_label,
        generated_at=generated_at,
        reports_dir=reports_dir,
        metadata_dir=metadata_dir,
    )
