import streamlit as st

from services.cost_estimator import estimate_report_cost
from services.model_profiles import (
    DEFAULT_ANALYSIS_MODE,
    MODE_NAMES,
    MODEL_OPTIONS,
    REASONING_EFFORT_OPTIONS,
    get_analysis_mode,
    get_default_profile,
    is_high_cost_profile,
    resolve_model_profile,
)
from services.output_languages import get_default_output_language, get_output_language, get_output_language_labels


def render_advanced_model_settings(*, analysis_mode: str, default_profile) -> tuple[bool, str, str]:
    override_model_settings = False
    model = default_profile.model
    reasoning_effort = default_profile.reasoning_effort
    with st.expander("Advanced model settings"):
        override_model_settings = st.checkbox("Override model settings", value=False)
        if override_model_settings:
            model = st.selectbox("Model", MODEL_OPTIONS, index=MODEL_OPTIONS.index(default_profile.model))
            reasoning_effort = st.selectbox(
                "Reasoning effort",
                REASONING_EFFORT_OPTIONS,
                index=REASONING_EFFORT_OPTIONS.index(default_profile.reasoning_effort),
            )
            manual_profile = resolve_model_profile(
                analysis_mode,
                override=True,
                model=model,
                reasoning_effort=reasoning_effort,
            )
            if is_high_cost_profile(manual_profile):
                st.warning("This manual model override may use more tokens and cost more.")
    return override_model_settings, model, reasoning_effort


def render_cost_estimate_panel(*, final_transcript: str, analysis_mode: str, selected_profile) -> bool:
    cost_confirmation_ok = True
    if final_transcript:
        estimate = estimate_report_cost(
            final_transcript,
            analysis_mode=analysis_mode,
            model=selected_profile.model,
            reasoning_effort=selected_profile.reasoning_effort,
        )
        with st.container(border=True):
            st.subheader("Cost & Token Estimate")
            st.caption("These are rough local estimates. No extra API call is made for this estimate.")
            col1, col2, col3 = st.columns(3)
            col1.metric("Transcript characters", f"{estimate.transcript_char_count:,}")
            col2.metric("Approx. transcript tokens", f"{estimate.approximate_transcript_tokens:,}")
            col3.metric("Rough cost level", estimate.cost_level)
            st.write(
                f"Analysis mode: `{estimate.analysis_mode}` | Model: `{estimate.model}` | "
                f"Reasoning effort: `{estimate.reasoning_effort}`"
            )
            for warning in estimate.warnings:
                st.warning(warning)
            if (st.session_state.get("prepared_transcript") or {}).get("source") == "audio_transcription":
                st.warning("This transcript was created with audio transcription fallback, which may have used additional API cost.")
            if estimate.requires_confirmation:
                cost_confirmation_ok = st.checkbox(
                    "I understand this may use more tokens.",
                    value=False,
                    key="cost-confirmation",
                )
    else:
        with st.container(border=True):
            st.subheader("Cost & Token Estimate")
            st.caption("Prepare a transcript first to see the estimate.")
    return cost_confirmation_ok


def render_configure_report_section(*, final_transcript: str) -> dict:
    st.header("Step 2: Configure Report")
    analysis_mode = st.selectbox(
        "Analysis Mode",
        MODE_NAMES,
        index=MODE_NAMES.index(DEFAULT_ANALYSIS_MODE),
    )
    selected_mode = get_analysis_mode(analysis_mode)
    output_language_labels = get_output_language_labels()
    default_output_language = get_default_output_language()
    selected_output_language_label = st.selectbox(
        "Report Output Language",
        output_language_labels,
        index=output_language_labels.index(default_output_language.label),
    )
    selected_output_language = get_output_language(selected_output_language_label)
    default_profile = get_default_profile(analysis_mode)

    override_model_settings, model, reasoning_effort = render_advanced_model_settings(
        analysis_mode=analysis_mode,
        default_profile=default_profile,
    )

    selected_profile = resolve_model_profile(
        analysis_mode,
        override=override_model_settings,
        model=model,
        reasoning_effort=reasoning_effort,
    )
    with st.container(border=True):
        st.subheader("Selected Model Profile")
        st.write(
            f"`{selected_profile.model}` / reasoning_effort=`{selected_profile.reasoning_effort}` "
            f"({selected_profile.use_case})"
        )
        st.caption(f"Output language: {selected_output_language.label}")
    if is_high_cost_profile(selected_profile):
        st.warning("This mode may use more tokens and cost more.")

    cost_confirmation_ok = render_cost_estimate_panel(
        final_transcript=final_transcript,
        analysis_mode=analysis_mode,
        selected_profile=selected_profile,
    )

    return {
        "analysis_mode": analysis_mode,
        "selected_mode": selected_mode,
        "selected_output_language": selected_output_language,
        "override_model_settings": override_model_settings,
        "selected_profile": selected_profile,
        "cost_confirmation_ok": cost_confirmation_ok,
    }
