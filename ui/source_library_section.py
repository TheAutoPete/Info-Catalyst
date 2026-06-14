import logging
from pathlib import Path

import streamlit as st

from services.report_archive import delete_report_record, read_metadata
from services.report_titles import backfill_title_metadata, needs_title_backfill, preview_title_backfill
from services.source_library import (
    build_filter_options,
    filter_library_records,
    load_library_records,
    search_library_records,
    sort_library_records,
)


def render_source_library_section(
    open_report,
    *,
    key_prefix: str = "source-library",
    show_debug: bool = False,
    result_limit: int = 25,
    show_heading: bool = True,
) -> None:
    if show_heading:
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
    st.caption(f"{len(matched_records)} matched of {len(records)} total report{'s' if len(records) != 1 else ''}")
    if not records:
        st.info("No saved reports yet.")
        _render_library_maintenance(records, key_prefix=key_prefix, show_debug=show_debug)
        return
    if not matched_records:
        st.info("No reports found.")
        _render_library_maintenance(records, key_prefix=key_prefix, show_debug=show_debug)
        return

    for index, record in enumerate(matched_records[:result_limit]):
        with st.container():
            st.markdown(f"**{record.display_title}**")
            details = [
                record.generated_at,
                record.analysis_mode,
                record.source_type,
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

            with st.expander("Delete this report"):
                st.warning(
                    "This permanently deletes the Markdown report and metadata JSON. "
                    "Transcript cache will not be deleted."
                )
                confirm_key = f"{key_prefix}-confirm-delete-{index}"
                confirmed = st.checkbox(
                    "I understand this deletion is permanent.",
                    key=confirm_key,
                )
                if st.button(
                    "Confirm delete report",
                    key=f"{key_prefix}-delete-report-{index}",
                    disabled=not confirmed,
                    use_container_width=True,
                ):
                    try:
                        result = delete_report_record(record)
                        if result["errors"]:
                            st.error("Report deletion was not completed. No unrelated files were deleted.")
                            if show_debug:
                                st.code("\n".join(result["errors"]))
                            return

                        selected_path = st.session_state.get("selected_report_path", "")
                        if selected_path and _same_path(Path(selected_path), record.report_path):
                            st.session_state.selected_report_path = ""
                        st.success("Report deleted.")
                        st.rerun()
                    except Exception as exc:
                        logging.exception("Failed to delete archived report: %s", record.report_path)
                        st.error("Could not delete that archived report.")
                        if show_debug:
                            st.code(f"{type(exc).__name__}: {exc}")

    if len(matched_records) > result_limit:
        st.caption(f"Showing the latest {result_limit} matched reports.")

    _render_library_maintenance(records, key_prefix=key_prefix, show_debug=show_debug)


def _render_library_maintenance(records, *, key_prefix: str, show_debug: bool, preview_limit: int = 10) -> None:
    eligible_records = [record for record in records if record.metadata_path]
    missing_records = [record for record in eligible_records if _record_needs_title_backfill(record)]

    with st.expander("Library maintenance"):
        st.caption(f"Total reports: {len(records)}")
        st.caption(f"Missing clean title metadata: {len(missing_records)}")

        if not records:
            st.info("No saved reports yet.")
            return
        if not missing_records:
            st.success("All reports already have clean title metadata.")
            return

        if st.button("Preview missing titles", key=f"{key_prefix}-preview-title-backfill", use_container_width=True):
            st.session_state[f"{key_prefix}-show-title-backfill-preview"] = True

        if st.session_state.get(f"{key_prefix}-show-title-backfill-preview"):
            _render_title_backfill_preview(missing_records[:preview_limit], total_count=len(missing_records))

        confirmed = st.checkbox(
            "I understand this will update metadata JSON files for reports missing title metadata.",
            key=f"{key_prefix}-confirm-title-backfill",
        )
        if st.button(
            "Backfill missing titles",
            key=f"{key_prefix}-backfill-missing-titles",
            disabled=not confirmed,
            use_container_width=True,
        ):
            updated_count = 0
            skipped_count = 0
            errors: list[str] = []
            for record in missing_records:
                try:
                    result = backfill_title_metadata(record.metadata_path, record.report_path)
                    if result.get("updated"):
                        updated_count += 1
                    else:
                        skipped_count += 1
                except Exception as exc:
                    logging.exception("Failed to backfill title metadata: %s", record.metadata_path)
                    skipped_count += 1
                    errors.append(f"{record.metadata_path}: {type(exc).__name__}: {exc}")

            st.success(f"Backfilled title metadata for {updated_count} report{'s' if updated_count != 1 else ''}.")
            if skipped_count:
                st.caption(f"Skipped {skipped_count} report{'s' if skipped_count != 1 else ''}.")
            if errors and show_debug:
                st.code("\n".join(errors))
            st.rerun()


def _record_needs_title_backfill(record) -> bool:
    try:
        return needs_title_backfill(_read_metadata_for_record(record))
    except Exception:
        logging.exception("Failed to inspect title metadata: %s", getattr(record, "metadata_path", ""))
        return False


def _render_title_backfill_preview(records, *, total_count: int) -> None:
    for record in records:
        preview = preview_title_backfill(record.metadata_path, record.report_path)
        proposed = preview["proposed"]
        st.markdown(f"**{preview['current_display_title']}**")
        st.caption(f"Proposed report_title: {proposed['report_title']}")
        st.caption(f"Proposed display_title: {proposed['display_title']}")
        st.caption(f"Metadata: {preview['metadata_path']}")
    if total_count > len(records):
        st.caption(f"Showing {len(records)} of {total_count} reports needing backfill.")


def _read_metadata_for_record(record) -> dict:
    return read_metadata(record.metadata_path)


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
    if record.source_type == "manual_text":
        if record.source_url:
            return f"Source URL: {record.source_url}"
        if record.source_title:
            return f"Source: {record.source_title}"
        return "Manual text source"
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


def _same_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return left == right
