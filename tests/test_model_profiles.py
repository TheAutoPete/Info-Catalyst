from services.model_profiles import get_analysis_mode, get_default_profile, is_high_cost_profile, resolve_model_profile


def test_investment_lens_uses_high_quality_profile_by_default():
    profile = get_default_profile("Investment Lens")

    assert profile.model == "gpt-5.5"
    assert profile.reasoning_effort == "high"
    assert is_high_cost_profile(profile)


def test_quick_summary_uses_fast_profile_by_default():
    profile = get_default_profile("Quick Summary")

    assert profile.model == "gpt-5.4-mini"
    assert profile.reasoning_effort == "low"


def test_manual_override_replaces_default_profile():
    profile = resolve_model_profile(
        "Deep Analysis",
        override=True,
        model="gpt-5.5",
        reasoning_effort="xhigh",
    )

    assert profile.model == "gpt-5.5"
    assert profile.reasoning_effort == "xhigh"
    assert profile.use_case == "manual override"


def test_legacy_titan_input_name_resolves_to_structured_research_label():
    mode = get_analysis_mode("Titan Input")

    assert mode.name == "Titan Input / Structured Research"
    assert mode.slug == "titan-input"
