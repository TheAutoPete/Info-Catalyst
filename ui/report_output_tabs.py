import logging
from pathlib import Path

import streamlit as st

from services.context_pack import context_pack_exists, save_context_pack
from services.report_archive import update_metadata
from services.transcript_cache import read_transcript_cache
from ui.components import (
    display_transcript_source,
    display_value,
    metadata_value,
    safe_metadata_for_display,
)


def render_context_pack_controls(
    *,
    report_text: str,
    report_path: Path,
    metadata_path: Path | None,
    metadata: dict,
    transcript_excerpt: str = "",
    key_prefix: str,
    show_debug_exception,
) -> None:
    if not report_text or not metadata_path:
        return

    st.subheader("Report Q&A Context Pack")
    st.caption("Creates a standalone Markdown file for copy/paste into your own AI assistant. No in-app chat is created.")
    existing_path = context_pack_exists(metadata)
    display_key = f"{key_prefix}-context-pack-text"

    col1, col2 = st.columns([1, 1])
    with col1:
        if existing_path:
            if st.button("Open existing Context Pack", key=f"{key_prefix}-open-context-pack"):
                st.session_state[display_key] = existing_path.read_text(encoding="utf-8")
                st.session_state[f"{display_key}-path"] = str(existing_path)
        else:
            if st.button("Generate Report Q&A Context Pack", key=f"{key_prefix}-generate-context-pack"):
                try:
                    new_path = save_context_pack(
                        report_text=report_text,
                        metadata=metadata,
                        report_path=report_path,
                        transcript_excerpt=transcript_excerpt,
                    )
                    updated_metadata = update_metadata(metadata_path, context_pack_path=str(new_path))
                    metadata.update(updated_metadata)
                    st.session_state[display_key] = new_path.read_text(encoding="utf-8")
                    st.session_state[f"{display_key}-path"] = str(new_path)
                    st.success(f"Context Pack saved to {new_path}")
                except Exception as exc:
                    logging.exception("Failed to generate context pack")
                    st.error("Could not generate the Context Pack.")
                    show_debug_exception(exc)

    with col2:
        if existing_path:
            if st.button("Regenerate Context Pack", key=f"{key_prefix}-regenerate-context-pack"):
                try:
                    new_path = save_context_pack(
                        report_text=report_text,
                        metadata=metadata,
                        report_path=report_path,
                        transcript_excerpt=transcript_excerpt,
                    )
                    updated_metadata = update_metadata(metadata_path, context_pack_path=str(new_path))
                    metadata.update(updated_metadata)
                    st.session_state[display_key] = new_path.read_text(encoding="utf-8")
                    st.session_state[f"{display_key}-path"] = str(new_path)
                    st.success(f"Context Pack regenerated at {new_path}")
                except Exception as exc:
                    logging.exception("Failed to regenerate context pack")
                    st.error("Could not regenerate the Context Pack.")
                    show_debug_exception(exc)

    context_text = st.session_state.get(display_key, "")
    if context_text:
        context_path = st.session_state.get(f"{display_key}-path", "")
        if context_path:
            st.caption(f"Context Pack path: {context_path}")
        st.markdown(context_text)
        st.download_button(
            "Download Context Pack Markdown",
            data=context_text,
            file_name=Path(context_path).name if context_path else "report-context-pack.md",
            mime="text/markdown",
            key=f"{key_prefix}-download-context-pack",
        )
        st.text_area(
            "Copy-friendly Context Pack",
            value=context_text,
            height=360,
            key=f"{key_prefix}-copy-context-pack",
        )


def render_report_settings_summary(metadata: dict) -> None:
    st.caption("Report settings")
    summary_fields = [
        ("Report title", metadata_value(metadata, "report_title")),
        ("Display title", metadata_value(metadata, "display_title")),
        ("Source title", metadata_value(metadata, "source_title", "video_title")),
        ("Title source", metadata_value(metadata, "title_source")),
        ("Analysis mode", metadata_value(metadata, "analysis_mode", "report_type")),
        ("Report output language", metadata_value(metadata, "output_language_label", "output_language")),
        ("Selected model", metadata_value(metadata, "selected_model")),
        ("Reasoning effort", metadata_value(metadata, "reasoning_effort")),
        ("Transcript source", display_transcript_source(metadata_value(metadata, "transcript_source"))),
        ("Transcript language", metadata_value(metadata, "transcript_language")),
        ("Generated", metadata_value(metadata, "generated_at")),
    ]
    cols = st.columns(2)
    for index, (label, value) in enumerate(summary_fields):
        cols[index % 2].write(f"**{label}:** `{display_value(value)}`")


def render_report_tab(*, report_text: str, report_path: Path | None, metadata: dict, key_prefix: str) -> None:
    st.markdown(report_text or "_No report content is available._")
    if report_path:
        st.caption(f"Report path: {report_path}")
        if report_text:
            st.download_button(
                "Download Report Markdown",
                data=report_text,
                file_name=report_path.name,
                mime="text/markdown",
                key=f"{key_prefix}-download-report",
            )
    render_report_settings_summary(metadata)


def render_metadata_tab(metadata: dict) -> None:
    if not metadata:
        st.info("Metadata is not available for this archived report.")
        return

    important_fields = {
        "report_title": metadata.get("report_title"),
        "display_title": metadata.get("display_title"),
        "source_title": metadata.get("source_title"),
        "title_source": metadata.get("title_source"),
        "title_generated_at": metadata.get("title_generated_at"),
        "source_url": metadata.get("source_url"),
        "video_id": metadata.get("video_id"),
        "video_title": metadata.get("video_title"),
        "transcript_source": metadata.get("transcript_source"),
        "transcript_provider": metadata.get("transcript_provider"),
        "transcript_language": metadata.get("transcript_language"),
        "transcript_cache_path": metadata.get("transcript_cache_path"),
        "analysis_mode": metadata.get("analysis_mode"),
        "report_output_language": metadata.get("output_language_label") or metadata.get("output_language"),
        "selected_model": metadata.get("selected_model"),
        "reasoning_effort": metadata.get("reasoning_effort"),
        "model_override": metadata.get("model_override"),
        "usage": metadata.get("usage"),
        "report_path": metadata.get("report_file_path"),
        "context_pack_path": metadata.get("context_pack_path"),
    }
    st.json(safe_metadata_for_display({key: value for key, value in important_fields.items() if value not in (None, "")}))
    with st.expander("All metadata"):
        st.json(safe_metadata_for_display(metadata))


def render_context_pack_tab(
    *,
    report_text: str,
    report_path: Path | None,
    metadata_path: Path | None,
    metadata: dict,
    transcript_excerpt: str,
    key_prefix: str,
    show_debug_exception,
) -> None:
    if not report_text or not report_path or not metadata_path:
        st.info("Context Pack controls are not available for this report.")
        return
    render_context_pack_controls(
        report_text=report_text,
        report_path=report_path,
        metadata_path=metadata_path,
        metadata=metadata,
        transcript_excerpt=transcript_excerpt,
        key_prefix=key_prefix,
        show_debug_exception=show_debug_exception,
    )


def _prepared_matches_metadata(prepared: dict, metadata: dict) -> bool:
    if not prepared:
        return False
    prepared_cache_path = str(prepared.get("cache_path") or "")
    metadata_cache_path = str(metadata.get("transcript_cache_path") or "")
    if prepared_cache_path and metadata_cache_path and prepared_cache_path == metadata_cache_path:
        return True
    return False


def _load_transcript_preview_text(metadata: dict, transcript_excerpt: str = "") -> tuple[str, str]:
    if transcript_excerpt:
        return transcript_excerpt, "current session"

    prepared = st.session_state.get("prepared_transcript") or {}
    if prepared.get("text") and _prepared_matches_metadata(prepared, metadata):
        return str(prepared.get("text") or ""), "current session"

    cache_path = metadata.get("transcript_cache_path")
    if cache_path:
        try:
            cached = read_transcript_cache(Path(cache_path))
        except OSError:
            cached = None
        if cached and cached.transcript_text:
            return cached.transcript_text, "local cache"
    return "", ""


def render_transcript_preview_tab(*, metadata: dict, transcript_excerpt: str = "") -> None:
    source = metadata_value(metadata, "transcript_source")
    provider = metadata_value(metadata, "transcript_provider")
    language = metadata_value(metadata, "transcript_language")
    cache_path = metadata_value(metadata, "transcript_cache_path")
    transcript_text, preview_source = _load_transcript_preview_text(metadata, transcript_excerpt)

    col1, col2, col3 = st.columns(3)
    col1.write(f"**Source:** `{display_value(display_transcript_source(source))}`")
    col2.write(f"**Provider:** `{display_value(provider)}`")
    col3.write(f"**Language:** `{display_value(language)}`")
    st.write(f"**Characters:** `{len(transcript_text):,}`")
    if cache_path:
        st.caption(f"Transcript cache path: {cache_path}")

    if not transcript_text:
        st.info("Transcript preview is not available for this archived report.")
        return

    preview_limit = 4000
    st.text_area(
        "Transcript preview",
        value=transcript_text[:preview_limit],
        height=260,
        disabled=True,
    )
    caption = f"Showing first {min(len(transcript_text), preview_limit):,} characters of {len(transcript_text):,}."
    if preview_source:
        caption += f" Loaded from {preview_source}."
    st.caption(caption)


def render_report_result_tabs(
    *,
    report_text: str,
    report_path: Path | None,
    metadata_path: Path | None,
    metadata: dict | None,
    transcript_excerpt: str = "",
    key_prefix: str,
    show_debug_exception,
) -> None:
    metadata = metadata or {}
    report_tab, metadata_tab, context_pack_tab, transcript_tab = st.tabs(
        ["Report", "Metadata", "Context Pack", "Transcript Preview"]
    )
    with report_tab:
        render_report_tab(
            report_text=report_text,
            report_path=report_path,
            metadata=metadata,
            key_prefix=key_prefix,
        )
    with metadata_tab:
        render_metadata_tab(metadata)
    with context_pack_tab:
        render_context_pack_tab(
            report_text=report_text,
            report_path=report_path,
            metadata_path=metadata_path,
            metadata=metadata,
            transcript_excerpt=transcript_excerpt,
            key_prefix=key_prefix,
            show_debug_exception=show_debug_exception,
        )
    with transcript_tab:
        render_transcript_preview_tab(metadata=metadata, transcript_excerpt=transcript_excerpt)
