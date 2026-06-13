import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from services.context_pack import build_context_pack, save_context_pack


def test_context_pack_contains_required_sections_and_rules():
    metadata = {
        "video_id": "abc12345678",
        "source_url": "https://youtu.be/abc12345678",
        "video_title": "AI Supply Chain",
        "analysis_mode": "Investment Lens",
        "selected_model": "gpt-5.5",
        "transcript_language": "en",
        "output_language": "zh-TW",
        "output_language_label": "Traditional Chinese",
    }

    content = build_context_pack(
        report_text="# Report\n\nReport body",
        metadata=metadata,
        report_path=Path("reports/markdown/report.md"),
        generated_at=datetime(2026, 6, 11, 8, 30),
    )

    assert "# Report Q&A Context Pack" in content
    assert "Source title: AI Supply Chain" in content
    assert "Source URL: https://youtu.be/abc12345678" in content
    assert "Video ID: abc12345678" in content
    assert "Report output language: Traditional Chinese" in content
    assert "## Instructions For External AI" in content
    assert "請使用台灣慣用繁體中文回答" in content
    assert "Use only the provided report and transcript excerpt." in content
    assert "Report body" in content
    assert "此 Context Pack 沒有附上逐字稿摘錄" in content
    assert "這份報告中最重要的三個結論是什麼？" in content


def test_context_pack_defaults_to_traditional_chinese_for_old_metadata():
    content = build_context_pack(
        report_text="# Report\n\nBody",
        metadata={"video_title": "Legacy Report"},
        generated_at=datetime(2026, 6, 11, 8, 30),
    )

    assert "Report output language: Traditional Chinese" in content
    assert "請使用台灣慣用繁體中文回答" in content
    assert "這份報告中最重要的三個結論是什麼？" in content


def test_context_pack_uses_selected_output_language_from_metadata():
    content = build_context_pack(
        report_text="# Report\n\nBody",
        metadata={"video_title": "English Report", "output_language": "en", "output_language_label": "English"},
        generated_at=datetime(2026, 6, 11, 8, 30),
    )

    assert "Report output language: English" in content
    assert "Answer in clear professional English." in content
    assert "What are the three most important conclusions in this report?" in content


def test_context_pack_uses_japanese_follow_up_questions():
    content = build_context_pack(
        report_text="# Report\n\nBody",
        metadata={"video_title": "Japanese Report", "output_language": "ja", "output_language_label": "Japanese"},
        generated_at=datetime(2026, 6, 11, 8, 30),
    )

    assert "Report output language: Japanese" in content
    assert "自然で専門的な日本語で回答してください" in content
    assert "このレポートで最も重要な結論を3つ挙げてください。" in content


def test_save_context_pack_writes_markdown_without_api_call():
    workspace = Path("tests") / ".tmp" / f"context-pack-{uuid.uuid4().hex}"
    context_dir = workspace / "reports" / "context"
    report_path = workspace / "reports" / "markdown" / "sample.md"
    report_path.parent.mkdir(parents=True)
    report_path.write_text("# Sample\n", encoding="utf-8")

    try:
        path = save_context_pack(
            report_text="# Sample\n\nBody",
            metadata=json.loads('{"video_title": "Sample"}'),
            report_path=report_path,
            context_dir=context_dir,
        )

        assert path.exists()
        assert path.parent == context_dir
        assert path.read_text(encoding="utf-8").startswith("# Report Q&A Context Pack")
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
