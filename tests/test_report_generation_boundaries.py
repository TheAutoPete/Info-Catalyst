from pathlib import Path


def test_report_generation_modules_do_not_call_youtube_or_transcript_provider_directly():
    for path in [
        Path("services") / "openai_client.py",
        Path("services") / "mode_prompts.py",
        Path("services") / "report_writer.py",
    ]:
        source = path.read_text(encoding="utf-8")

        assert "youtube_transcript_api" not in source
        assert "YouTubeTranscriptApi" not in source
        assert "fetch_transcript" not in source
        assert "from services import transcript_provider" not in source
        assert "import transcript_provider" not in source
