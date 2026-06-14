import streamlit as st

from services.report_archive import list_recent_reports


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


def render_sidebar(open_report) -> bool:
    with st.sidebar:
        with st.expander("Debug options"):
            show_debug = st.checkbox("Show debug info", value=False)
            st.caption("Shows transcript diagnostics and exception tracebacks when errors occur.")
        render_recent_reports_sidebar(open_report)
    return show_debug
