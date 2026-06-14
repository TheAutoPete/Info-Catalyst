import json

from services.report_titles import (
    backfill_title_metadata,
    build_title_backfill_payload,
    needs_title_backfill,
    preview_title_backfill,
)


def test_needs_title_backfill_returns_true_when_title_fields_are_missing():
    assert needs_title_backfill({"video_title": "Legacy Video"})


def test_needs_title_backfill_returns_false_when_title_fields_exist():
    metadata = {
        "report_title": "Clean Report",
        "display_title": "2026-06-10 12:00 - Clean Report - Quick Summary",
        "title_source": "report_h1",
        "title_generated_at": "2026-06-10T12:00:00",
    }

    assert not needs_title_backfill(metadata)


def test_needs_title_backfill_returns_false_for_complete_fallback_title_metadata():
    metadata = {
        "report_title": "Untitled report",
        "display_title": "2026-06-10 12:00 - Untitled report - Quick Summary",
        "title_source": "fallback",
        "title_generated_at": "2026-06-10T12:00:00",
    }

    assert not needs_title_backfill(metadata)


def test_backfill_payload_uses_useful_markdown_h1():
    payload = build_title_backfill_payload(
        {"generated_at": "2026-06-10T12:00:00", "analysis_mode": "Quick Summary"},
        markdown_text="# AI Datacenter Power Bottleneck\nBody",
        file_stem="legacy",
    )

    assert payload["report_title"] == "AI Datacenter Power Bottleneck"
    assert payload["title_source"] == "report_h1"


def test_backfill_payload_ignores_generic_markdown_h1():
    payload = build_title_backfill_payload(
        {"video_title": "Real Video Title", "generated_at": "2026-06-10T12:00:00"},
        markdown_text="# Summary Report\nBody",
        file_stem="legacy",
    )

    assert payload["report_title"] == "Real Video Title"
    assert payload["title_source"] == "video_title"


def test_backfill_payload_falls_back_to_video_title():
    payload = build_title_backfill_payload(
        {"video_title": "Video Title", "generated_at": "2026-06-10T12:00:00"},
        markdown_text="Body only",
        file_stem="legacy",
    )

    assert payload["report_title"] == "Video Title"


def test_backfill_payload_falls_back_to_source_title():
    payload = build_title_backfill_payload(
        {"source_title": "Source Title", "generated_at": "2026-06-10T12:00:00"},
        markdown_text="Body only",
        file_stem="legacy",
    )

    assert payload["report_title"] == "Source Title"
    assert payload["title_source"] == "source_title"


def test_backfill_payload_falls_back_to_video_id_or_file_stem():
    video_id_payload = build_title_backfill_payload(
        {"video_id": "abc12345678", "generated_at": "2026-06-10T12:00:00"},
        markdown_text="Body only",
        file_stem="legacy-title",
    )
    stem_payload = build_title_backfill_payload(
        {"generated_at": "2026-06-10T12:00:00"},
        markdown_text="Body only",
        file_stem="2026-06-10_1200_legacy-title",
    )

    assert video_id_payload["report_title"] == "abc12345678"
    assert stem_payload["report_title"] == "legacy title"


def test_existing_non_empty_report_title_is_preserved():
    payload = build_title_backfill_payload(
        {"report_title": "Pinned Report Title", "video_title": "Video Title", "generated_at": "2026-06-10T12:00:00"},
        markdown_text="Body only",
        file_stem="legacy",
    )

    assert payload["report_title"] == "Pinned Report Title"


def test_existing_generic_report_title_can_be_replaced_when_backfilling():
    payload = build_title_backfill_payload(
        {"report_title": "Summary Report", "video_title": "Video Title", "generated_at": "2026-06-10T12:00:00"},
        markdown_text="# Useful H1\nBody",
        file_stem="legacy",
    )

    assert payload["report_title"] == "Useful H1"


def test_backfill_payload_builds_display_title():
    payload = build_title_backfill_payload(
        {"video_title": "Video Title", "generated_at": "2026-06-10T12:00:00", "analysis_mode": "Deep Analysis"},
        markdown_text="Body only",
        file_stem="legacy",
    )

    assert payload["display_title"] == "2026-06-10 12:00 - Video Title - Deep Analysis"


def test_metadata_write_preserves_unrelated_fields(tmp_path):
    report_path = tmp_path / "legacy.md"
    metadata_path = tmp_path / "legacy.json"
    report_path.write_text("# Useful H1\nBody\n", encoding="utf-8")
    metadata_path.write_text(
        json.dumps(
            {
                "video_id": "abc12345678",
                "usage": [{"total_tokens": 120}],
                "source_url": "https://youtu.be/abc12345678",
                "transcript_cache_path": "reports/transcripts/abc12345678.json",
                "selected_model": "gpt-5.4-mini",
                "output_language": "zh-TW",
                "context_pack_path": "reports/context/sample.md",
                "generated_at": "2026-06-10T12:00:00",
            }
        ),
        encoding="utf-8",
    )

    result = backfill_title_metadata(metadata_path, report_path)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    assert result["updated"]
    assert metadata["report_title"] == "Useful H1"
    assert metadata["usage"] == [{"total_tokens": 120}]
    assert metadata["source_url"] == "https://youtu.be/abc12345678"
    assert metadata["transcript_cache_path"] == "reports/transcripts/abc12345678.json"
    assert metadata["selected_model"] == "gpt-5.4-mini"
    assert metadata["output_language"] == "zh-TW"
    assert metadata["context_pack_path"] == "reports/context/sample.md"


def test_utf8_json_write_uses_ensure_ascii_false(tmp_path):
    report_path = tmp_path / "legacy.md"
    metadata_path = tmp_path / "legacy.json"
    report_path.write_text("# 台積電供應鏈更新\nBody\n", encoding="utf-8")
    metadata_path.write_text(json.dumps({"generated_at": "2026-06-10T12:00:00"}), encoding="utf-8")

    backfill_title_metadata(metadata_path, report_path)
    raw_json = metadata_path.read_text(encoding="utf-8")

    assert "台積電供應鏈更新" in raw_json
    assert "\\u53f0" not in raw_json


def test_missing_markdown_file_is_handled_gracefully(tmp_path):
    report_path = tmp_path / "missing.md"
    metadata_path = tmp_path / "legacy.json"
    metadata_path.write_text(
        json.dumps({"video_title": "Legacy Video", "generated_at": "2026-06-10T12:00:00"}),
        encoding="utf-8",
    )

    preview = preview_title_backfill(metadata_path, report_path)
    result = backfill_title_metadata(metadata_path, report_path)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    assert preview["missing_report"]
    assert result["updated"]
    assert metadata["report_title"] == "Legacy Video"
