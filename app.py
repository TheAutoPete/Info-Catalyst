import importlib
import logging
import traceback
from pathlib import Path

import streamlit as st

from config import LOGS_DIR
from services import mode_prompts as _mode_prompts
from services import openai_client as _openai_client
from services import report_writer as _report_writer
from services.report_archive import (
    find_report_record_by_path,
    read_metadata,
    read_report,
)
from ui.report_config_section import render_configure_report_section
from ui.report_output_tabs import render_report_result_tabs
from ui.sidebar import render_sidebar
from ui.source_section import render_prepare_source_section


mode_prompts = importlib.reload(_mode_prompts)
add_report_header = mode_prompts.add_report_header
build_mode_report_prompt = mode_prompts.build_mode_report_prompt
openai_client = importlib.reload(_openai_client)
OpenAIRequestError = openai_client.OpenAIRequestError
generate_markdown_with_usage = openai_client.generate_markdown_with_usage
report_writer = importlib.reload(_report_writer)
save_report_with_metadata = report_writer.save_report_with_metadata


def configure_logging() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=LOGS_DIR / "app.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def show_debug_exception(exc: Exception) -> None:
    if show_debug_info:
        st.code(f"{type(exc).__name__}: {exc}")
        st.code("".join(traceback.format_exception(exc)))


def open_report(path: Path) -> None:
    st.session_state.selected_report_path = str(path)


def initialize_session_state() -> None:
    if "selected_report_path" not in st.session_state:
        st.session_state.selected_report_path = ""
    if "prepared_transcript" not in st.session_state:
        st.session_state.prepared_transcript = None
    if "prepared_video_id" not in st.session_state:
        st.session_state.prepared_video_id = ""
    if "transcript_debug_messages" not in st.session_state:
        st.session_state.transcript_debug_messages = []
    if "last_youtube_fetch_at" not in st.session_state:
        st.session_state.last_youtube_fetch_at = {}


def render_archived_report() -> None:
    selected_report_path = st.session_state.get("selected_report_path", "")
    if not selected_report_path:
        return

    try:
        selected_path = Path(selected_report_path)
        selected_record = find_report_record_by_path(selected_path)
        selected_metadata = read_metadata(selected_record.metadata_path if selected_record else None)
        selected_report = read_report(selected_path)
        st.subheader("Archived Report")
        render_report_result_tabs(
            report_text=selected_report,
            report_path=selected_path,
            metadata_path=selected_record.metadata_path if selected_record else None,
            metadata=selected_metadata,
            key_prefix=f"report-{selected_path.stem}",
            show_debug_exception=show_debug_exception,
        )
        st.divider()
    except Exception as exc:
        logging.exception("Failed to open archived report: %s", selected_report_path)
        st.error("Could not open that archived report.")
        show_debug_exception(exc)


def render_generate_export_section(*, source_state: dict, report_state: dict) -> None:
    final_transcript = source_state["final_transcript"]
    duplicate_reports = source_state["duplicate_reports"]
    generate_duplicate_report = source_state["generate_duplicate_report"]
    cost_confirmation_ok = report_state["cost_confirmation_ok"]

    st.header("Step 3: Generate & Export")
    generate = st.button(
        "Generate Report",
        type="primary",
        disabled=(
            not final_transcript
            or (bool(duplicate_reports) and not generate_duplicate_report)
            or not cost_confirmation_ok
        ),
    )

    if not generate:
        return

    try:
        selected_mode = report_state["selected_mode"]
        selected_profile = report_state["selected_profile"]
        selected_output_language = report_state["selected_output_language"]
        analysis_mode = report_state["analysis_mode"]
        override_model_settings = report_state["override_model_settings"]
        youtube_url = source_state["youtube_url"]
        video_title = source_state["video_title"]
        video_id = source_state["video_id"]
        transcript_language = source_state["transcript_language"]

        models_used = {
            selected_mode.slug: selected_profile.model,
        }
        archive_video_id = video_id or "manual-transcript"
        report_type = selected_mode.slug
        prepared = st.session_state.get("prepared_transcript") or {}
        prompt = build_mode_report_prompt(
            final_transcript,
            youtube_url,
            analysis_mode=analysis_mode,
            profile=selected_profile,
            output_language=selected_output_language.code,
        )

        with st.spinner(f"Generating {analysis_mode} report..."):
            generation = generate_markdown_with_usage(
                prompt,
                model=selected_profile.model,
                reasoning_effort=selected_profile.reasoning_effort,
                analysis_mode=analysis_mode,
            )
            report = generation.text
            report = add_report_header(
                report,
                analysis_mode=analysis_mode,
                model=selected_profile.model,
                reasoning_effort=selected_profile.reasoning_effort,
                override=override_model_settings,
                output_language_label=selected_output_language.label,
            )
            report_path = save_report_with_metadata(
                report_type,
                report,
                video_id=archive_video_id,
                source_url=youtube_url,
                video_title=video_title,
                transcript_language=transcript_language,
                models=models_used,
                analysis_mode=analysis_mode,
                selected_model=selected_profile.model,
                reasoning_effort=selected_profile.reasoning_effort,
                model_override=override_model_settings,
                usage=[generation.usage],
                transcript_source=prepared.get("source", ""),
                transcript_provider=prepared.get("provider", ""),
                transcript_cache_path=prepared.get("cache_path", ""),
                transcript_created_at=prepared.get("created_at", ""),
                output_language=selected_output_language.code,
                output_language_label=selected_output_language.label,
            )

        st.session_state.selected_report_path = str(report_path)
        saved_record = find_report_record_by_path(report_path)
        saved_metadata = read_metadata(saved_record.metadata_path if saved_record else None)
        st.subheader(f"{analysis_mode} Report")
        render_report_result_tabs(
            report_text=report,
            report_path=report_path,
            metadata_path=saved_record.metadata_path if saved_record else None,
            metadata=saved_metadata,
            transcript_excerpt=final_transcript,
            key_prefix=f"report-{report_path.stem}",
            show_debug_exception=show_debug_exception,
        )
    except OpenAIRequestError as exc:
        logging.exception("Report generation failed")
        st.error(str(exc))
        show_debug_exception(exc)
    except Exception as exc:
        logging.exception("Report generation failed")
        st.error("Report generation failed. Please check your API key, model setting, or transcript input and try again.")
        show_debug_exception(exc)


configure_logging()
st.set_page_config(page_title="Info Catalyst", layout="wide")


st.title("Info Catalyst")
st.caption("Private MVP for turning YouTube transcripts into AI research reports.")

initialize_session_state()
show_debug_info = render_sidebar(open_report)
render_archived_report()
source_state = render_prepare_source_section(
    show_debug=show_debug_info,
    open_report=open_report,
    show_debug_exception=show_debug_exception,
)
report_state = render_configure_report_section(final_transcript=source_state["final_transcript"])
render_generate_export_section(source_state=source_state, report_state=report_state)
