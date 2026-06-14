from pathlib import Path

import streamlit as st

from services.report_archive import list_recent_reports
from services.source_library import (
    build_filter_options,
    filter_library_records,
    load_library_records,
    search_library_records,
    sort_library_records,
)


def render_recent_reports_sidebar(open_report) -> None:
    st.subheader("Recent Reports")
    recent_reports = list_recent_reports(limit=20)
    if recent_reports:
        for index, record in enumerate(recent_reports):
            label = record.display_title
            if st.button(label, key=f"recent-report-{index}", use_container_width=True):
                open_report(record.report_path)
    else:
        st.caption("No saved reports yet.")


def render_source_library_sidebar(open_report) -> None:
    with st.expander("Source Library"):
        records = load_library_records()
        if st.button("Clear filters", key="source-library-clear-filters", use_container_width=True):
            st.session_state["source-library-search"] = ""
            st.session_state["source-library-analysis-mode"] = "All"
            st.session_state["source-library-output-language-label"] = "All"
            st.session_state["source-library-transcript-source"] = "All"
            st.session_state["source-library-transcript-language"] = "All"
            st.session_state["source-library-source-type"] = "All"
            st.rerun()

        search_query = st.text_input("Search reports", key="source-library-search")

        filters = {
            "analysis_mode": st.selectbox(
                "Analysis Mode",
                build_filter_options(records, "analysis_mode"),
                key="source-library-analysis-mode",
            ),
            "output_language_label": st.selectbox(
                "Output Language",
                build_filter_options(records, "output_language_label"),
                key="source-library-output-language-label",
            ),
            "transcript_source": st.selectbox(
                "Transcript Source",
                build_filter_options(records, "transcript_source"),
                key="source-library-transcript-source",
            ),
            "transcript_language": st.selectbox(
                "Transcript Language",
                build_filter_options(records, "transcript_language"),
                key="source-library-transcript-language",
            ),
            "source_type": st.selectbox(
                "Source Type",
                build_filter_options(records, "source_type"),
                key="source-library-source-type",
            ),
        }

        matched_records = sort_library_records(filter_library_records(search_library_records(records, search_query), filters))
        st.caption(f"{len(matched_records)} matched report{'s' if len(matched_records) != 1 else ''}")
        if not matched_records:
            st.info("No reports found.")
            return

        for index, record in enumerate(matched_records[:25]):
            with st.container():
                st.markdown(f"**{record.display_title}**")
                details = [
                    record.generated_at,
                    record.analysis_mode,
                    record.output_language_label,
                    record.transcript_source,
                ]
                st.caption(" | ".join(part for part in details if part))
                st.caption(record.source_url or record.video_id or "Unknown source")

                report_col, context_col = st.columns(2)
                with report_col:
                    if st.button("Open Report", key=f"source-library-open-report-{index}", use_container_width=True):
                        open_report(record.report_path)
                        st.rerun()
                with context_col:
                    if _context_pack_available(record.context_pack_path):
                        if st.button(
                            "Open Context Pack",
                            key=f"source-library-open-context-{index}",
                            use_container_width=True,
                        ):
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


def render_sidebar(open_report) -> bool:
    with st.sidebar:
        with st.expander("Debug options"):
            show_debug = st.checkbox("Show debug info", value=False)
            st.caption("Shows transcript diagnostics and exception tracebacks when errors occur.")
        render_recent_reports_sidebar(open_report)
        render_source_library_sidebar(open_report)
    return show_debug
