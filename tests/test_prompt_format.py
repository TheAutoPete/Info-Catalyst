from services.analyst import build_analysis_prompt
from services.mode_prompts import build_mode_report_prompt
from services.model_profiles import get_default_profile
from services.prompt_loader import format_prompt
from services.summarizer import build_summary_prompt


def test_format_prompt_inserts_source_and_transcript():
    prompt = format_prompt("URL: {source_url}\nTranscript: {transcript}", transcript=" hello ", source_url="https://youtu.be/id")

    assert "URL: https://youtu.be/id" in prompt
    assert "Transcript: hello" in prompt


def test_summary_prompt_contains_required_sections():
    prompt = build_summary_prompt("Transcript body", "https://youtu.be/dQw4w9WgXcQ")

    assert "Taiwan-style Traditional Chinese" in prompt
    assert "Do not output Simplified Chinese" in prompt
    assert "# Summary Report" in prompt
    assert "## Executive Summary" in prompt
    assert "## Key Points" in prompt
    assert "## Important Claims" in prompt
    assert "## Mentioned Companies / People / Technologies" in prompt
    assert "## One-minute Takeaway" in prompt
    assert "Transcript body" in prompt


def test_analysis_prompt_contains_required_sections():
    prompt = build_analysis_prompt("Transcript body", "https://youtu.be/dQw4w9WgXcQ")

    assert "Taiwan-style Traditional Chinese" in prompt
    assert "Do not output Simplified Chinese" in prompt
    assert "# Deep Analysis Report" in prompt
    assert "## Core Thesis" in prompt
    assert "## Argument Quality" in prompt
    assert "## Possible Biases" in prompt
    assert "## Missing Context" in prompt
    assert "## Counterarguments" in prompt
    assert "## Investment / Intelligence Implications" in prompt
    assert "## What To Verify Next" in prompt
    assert "Transcript body" in prompt


def test_mode_prompt_contains_shared_language_requirement():
    prompt = build_mode_report_prompt(
        "Transcript body",
        "https://youtu.be/dQw4w9WgXcQ",
        analysis_mode="Investment Lens",
        profile=get_default_profile("Investment Lens"),
    )

    assert "Final output must be in Taiwan-style Traditional Chinese." in prompt
    assert "Convert Simplified Chinese terms to Traditional Chinese." in prompt
    assert "## 投資摘要" in prompt
    assert "## 對 portfolio / watchlist 的啟示" in prompt
    assert "model: gpt-5.5" in prompt
    assert "reasoning_effort: high" in prompt
    assert "Transcript body" in prompt
