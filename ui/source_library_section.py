from pathlib import Path

import streamlit as st

from services.source_library import (
    build_filter_options,
    filter_library_records,
    load_library_records,
    search_library_records,
    sort_library_records,
)


def render_source_library_section(open_report, *, key_prefix: str = "source-library") -> None:
    st.subheader("Source Library")
    records = load_library_records()
    if st.button("Clear Source Library filters", key=f"{key_prefix}-clear-filters", use_container_width=True):
        st.session_state[f"{key_prefix}-search"] = ""
        st.session_state[f"{key_prefix}-analysis-mode"] = "All"
        st.session_state[f"{key_prefix}-output-language-label"] = "All"
        st.session_state[f"{key_prefix}-transcript-source"] = "All"
        st.rerun()

    search_query = st.text_input("Search reports", key=f"{key_prefix}-search")

    analysis_mode_options = build_filter_options(records, "analysis_mode")
    output_language_options = build_filter_options(records, "output_language_label")
    transcript_source_options = build_filter_options(records, "transcript_source")
    _ensure_filter_state(f"{key_prefix}-analysis-mode", analysis_mode_options)
    _ensure_filter_state(f"{key_prefix}-output-language-label", output_language_options)
    _ensure_filter_state(f"{key_prefix}-transcript-source", transcript_source_options)

    filters = {
        "analysis_mode": st.selectbox(
            "Analysis Mode",
            analysis_mode_options,
            key=f"{key_prefix}-analysis-mode",
        ),
        "output_language_label": st.selectbox(
            "Output Language",
            output_language_options,
            key=f"{key_prefix}-output-language-label",
        ),
        "transcript_source": st.selectbox(
            "Transcript Source",
            transcript_source_options,
            key=f"{key_prefix}-transcript-source",
        ),
    }

    matched_records = sort_library_records(filter_library_records(search_library_records(records, search_query), filters))
    st.caption(f"{len(matched_records)} matched report{'s' if len(matched_records) != 1 else ''}")
    if not records:
        st.info("No saved reports yet.")
        return
    if not matched_records:
        st.info("No reports found.")
        return

    for index, record in enumerate(matched_records[:25]):
        with st.container():
            st.markdown(f"**{record.display_title}**")
            details = [
                record.generated_at,
                record.analysis_mode,
                _output_language_display(record),
                record.transcript_source,
            ]
            st.caption(" | ".join(part for part in details if part))
            st.caption(_source_display(record))

            report_col, context_col = st.columns(2)
            with report_col:
                if st.button("Open Report", key=f"{key_prefix}-open-report-{index}", use_container_width=True):
                    open_report(record.report_path)
                    st.rerun()
            with context_col:
                if _context_pack_available(record.context_pack_path):
                    if st.button(
                        "Open Context Pack",
                        key=f"{key_prefix}-open-context-{index}",
                        use_container_width=True,
                    ):
                        _open_context_pack(record)
                        open_report(record.report_path)
                        st.rerun()
                else:
                    st.caption("No Context Pack")

    if len(matched_records) > 25:
        st.caption("Showing the latest 25 matched reports.")


def _context_pack_available(path_text: str) -> bool:
    if not path_text:
        return False
    try:
        return Path(path_text).exists()
    except OSError:
        return False


def _ensure_filter_state(key: str, options: list[str]) -> None:
    if st.session_state.get(key, "All") not in options:
        st.session_state[key] = "All"


def _output_language_display(record) -> str:
    return record.output_language_label if record.output_language_label != "Unknown" else record.output_language


def _source_display(record) -> str:
    if record.video_id:
        return f"Video ID: {record.video_id}"
    if record.source_url:
        return f"Source URL: {record.source_url}"
    return "Unknown source"


def _open_context_pack(record) -> None:
    context_path = Path(record.context_pack_path)
    display_key = f"report-{record.report_path.stem}-context-pack-text"
    st.session_state[display_key] = context_path.read_text(encoding="utf-8")
    st.session_state[f"{display_key}-path"] = str(context_path)
