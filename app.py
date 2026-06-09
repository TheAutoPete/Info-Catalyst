import streamlit as st

from services.analyst import generate_deep_analysis_report
from services.report_writer import save_report
from services.summarizer import generate_summary_report
from services.transcript_provider import (
    TRANSLATION_TARGETS,
    TranscriptError,
    fetch_transcript_result,
    format_debug_exception,
    get_transcript_options,
)
from services.url_parser import YouTubeUrlError, extract_video_id


st.set_page_config(page_title="Info Catalyst", layout="wide")

st.title("Info Catalyst")
st.caption("Private MVP for turning YouTube transcripts into AI research reports.")

youtube_url = st.text_input("YouTube URL", placeholder="https://www.youtube.com/watch?v=...")

transcript = ""
video_id = None
transcript_error = None
debug_messages = []
transcript_options = None

if youtube_url:
    try:
        video_id = extract_video_id(youtube_url)
        st.caption(f"Parsed YouTube video ID: `{video_id}`")
        transcript_options = get_transcript_options(video_id)
        debug_messages.extend(transcript_options.debug_messages)

        if transcript_options.available_transcripts:
            st.caption(
                "Available transcript languages: "
                + ", ".join(item.display_label for item in transcript_options.available_transcripts)
            )
        if transcript_options.selected_transcript:
            st.caption(f"Selected transcript language: `{transcript_options.selected_transcript.language_code}`")
            st.caption(f"Selected transcript type: {transcript_options.selected_transcript.kind}")

        translate_to = None
        if transcript_options.selected_transcript and transcript_options.selected_transcript.is_translatable:
            supported_translations = {
                code: label
                for code, label in TRANSLATION_TARGETS.items()
                if code in {lang_code for lang_code, _ in transcript_options.selected_transcript.translation_languages}
            }
            if supported_translations:
                translation_choice = st.selectbox(
                    "Optional transcript translation for debug/fallback",
                    ["Original"] + list(supported_translations.values()),
                )
                translate_to = next(
                    (code for code, label in supported_translations.items() if label == translation_choice),
                    None,
                )

        transcript_result = fetch_transcript_result(video_id, translate_to=translate_to)
        transcript = transcript_result.text
        debug_messages.extend(transcript_result.debug_messages)
        st.success(f"Transcript extracted from {transcript_result.selected_transcript.display_label}.")
        st.caption(f"Selected transcript language: `{transcript_result.selected_transcript.language_code}`")
        st.caption(f"Selected transcript type: {transcript_result.selected_transcript.kind}")
    except (YouTubeUrlError, TranscriptError) as exc:
        transcript_error = str(exc)
        debug_messages.extend(getattr(exc, "debug_messages", ()) or (format_debug_exception(exc),))
        st.warning(transcript_error)

if youtube_url and debug_messages:
    with st.expander("Transcript debug info"):
        for message in debug_messages:
            st.code(message)

manual_transcript = st.text_area(
    "Manual transcript fallback",
    value="" if transcript else "",
    height=220,
    placeholder="Paste the transcript here if automatic extraction fails.",
)

final_transcript = transcript or manual_transcript.strip()

if final_transcript:
    st.subheader("Transcript Preview")
    st.text_area(
        "Preview",
        value=final_transcript[:4000],
        height=260,
        disabled=True,
        label_visibility="collapsed",
    )
    if len(final_transcript) > 4000:
        st.caption(f"Showing first 4,000 characters of {len(final_transcript):,}.")
elif youtube_url and transcript_error:
    st.info("Paste a transcript above to continue.")

generate = st.button(
    "Generate Reports",
    type="primary",
    disabled=not final_transcript,
)

if generate:
    source_label = video_id or "manual-transcript"
    with st.spinner("Generating Summary Report..."):
        summary_report = generate_summary_report(final_transcript, source_url=youtube_url)
        summary_path = save_report("summary", summary_report, source_label)

    with st.spinner("Generating Deep Analysis Report..."):
        analysis_report = generate_deep_analysis_report(final_transcript, source_url=youtube_url)
        analysis_path = save_report("deep-analysis", analysis_report, source_label)

    left, right = st.columns(2)
    with left:
        st.subheader("Summary Report")
        st.markdown(summary_report)
        st.caption(f"Saved to {summary_path}")
    with right:
        st.subheader("Deep Analysis Report")
        st.markdown(analysis_report)
        st.caption(f"Saved to {analysis_path}")
