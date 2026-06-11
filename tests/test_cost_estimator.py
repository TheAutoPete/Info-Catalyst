from services.cost_estimator import classify_cost_level, estimate_report_cost, estimate_tokens


def test_estimate_tokens_is_local_and_approximate():
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd" * 8) == 10


def test_low_cost_quick_summary_does_not_require_confirmation():
    estimate = estimate_report_cost(
        "short transcript",
        analysis_mode="Quick Summary",
        model="gpt-5.4-mini",
        reasoning_effort="low",
    )

    assert estimate.cost_level == "Low"
    assert estimate.requires_confirmation is False


def test_expensive_model_and_high_effort_are_high_cost():
    level = classify_cost_level(
        9_000,
        char_count=28_800,
        analysis_mode="Deep Analysis",
        model="gpt-5.5",
        reasoning_effort="high",
    )

    assert level == "High"


def test_investment_lens_long_transcript_warns_and_requires_confirmation():
    estimate = estimate_report_cost(
        "a" * 60_000,
        analysis_mode="Investment Lens",
        model="gpt-5.5",
        reasoning_effort="high",
    )

    assert estimate.cost_level == "Very High"
    assert estimate.requires_confirmation is True
    assert any("Investment Lens" in warning for warning in estimate.warnings)
