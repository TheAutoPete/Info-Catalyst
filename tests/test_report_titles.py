from datetime import datetime

from services.report_titles import (
    build_display_title,
    build_safe_report_filename,
    extract_report_title,
    is_generic_report_title,
    resolve_report_title,
    sanitize_report_filename_part,
)


def test_extract_report_title_from_first_markdown_h1():
    title = extract_report_title("## Settings\n\n# AI Datacenter Power Bottleneck\n\nBody")

    assert title == "AI Datacenter Power Bottleneck"


def test_extract_report_title_ignores_generic_h1():
    title = extract_report_title("# Summary Report\n\nBody")

    assert title == ""
    assert is_generic_report_title("Investment Lens Report")


def test_resolve_report_title_falls_back_when_h1_missing():
    resolved = resolve_report_title(
        markdown_text="No heading",
        source_title="AI Supply Chain Update",
        video_id="Y-1vYPCSP24",
        analysis_mode="Deep Analysis",
        generated_at=datetime(2026, 6, 13, 15, 30),
    )

    assert resolved["report_title"] == "AI Supply Chain Update"
    assert resolved["title_source"] == "source_title"


def test_build_display_title_uses_timestamp_title_and_analysis_mode():
    display_title = build_display_title(
        report_title="AI Datacenter Power Bottleneck",
        generated_at=datetime(2026, 6, 13, 15, 30),
        analysis_mode="Investment Lens",
    )

    assert display_title == "2026-06-13 15:30 - AI Datacenter Power Bottleneck - Investment Lens"


def test_sanitize_report_filename_part_removes_windows_invalid_characters():
    sanitized = sanitize_report_filename_part('AI: Datacenter / Power? "Bottleneck"*')

    assert sanitized == "AI-Datacenter-Power-Bottleneck"
    assert not any(char in sanitized for char in '<>:"/\\|?*')


def test_build_safe_report_filename_keeps_length_reasonable():
    filename = build_safe_report_filename(
        generated_at=datetime(2026, 6, 13, 15, 30),
        analysis_mode="Investment Lens",
        report_title="AI Datacenter Power Bottleneck " * 20,
        source_id="Y-1vYPCSP24",
    )

    assert filename.startswith("2026-06-13_1530_investment-lens_ai-datacenter-power-bottleneck")
    assert filename.endswith("_Y-1vYPCSP24.md")
    assert len(filename) <= 180
