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
    }

    content = build_context_pack(
        report_text="# Report\n\n報告內容",
        metadata=metadata,
        report_path=Path("reports/markdown/report.md"),
        generated_at=datetime(2026, 6, 11, 8, 30),
    )

    assert "# Report Q&A Context Pack" in content
    assert "Source title: AI Supply Chain" in content
    assert "Source URL: https://youtu.be/abc12345678" in content
    assert "Video ID: abc12345678" in content
    assert "給外部 AI 助理的使用指令" in content
    assert "台灣慣用繁體中文" in content
    assert "不要捏造" in content
    assert "報告內容" in content
    assert "本 Context Pack 預設不包含完整逐字稿" in content
    assert "這份內容最值得驗證的三個關鍵假設是什麼？" in content


def test_save_context_pack_writes_markdown_without_api_call():
    workspace = Path("tests") / ".tmp" / f"context-pack-{uuid.uuid4().hex}"
    context_dir = workspace / "reports" / "context"
    report_path = workspace / "reports" / "markdown" / "sample.md"
    report_path.parent.mkdir(parents=True)
    report_path.write_text("# Sample\n", encoding="utf-8")

    try:
        path = save_context_pack(
            report_text="# Sample\n\n內容",
            metadata=json.loads('{"video_title": "Sample"}'),
            report_path=report_path,
            context_dir=context_dir,
        )

        assert path.exists()
        assert path.parent == context_dir
        assert path.read_text(encoding="utf-8").startswith("# Report Q&A Context Pack")
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
