import importlib
import logging
import traceback
from datetime import datetime
from pathlib import Path

import streamlit as st

from config import LOGS_DIR
from services import mode_prompts as _mode_prompts
from services import model_profiles as _model_profiles
from services import openai_client as _openai_client
from services import output_languages as _output_languages
from services import report_writer as _report_writer
from services import transcript_provider as _transcript_provider
from services import transcript_cache as _transcript_cache
from services import cost_estimator as _cost_estimator
from services import context_pack as _context_pack
from services.report_archive import (
    find_report_record_by_path,
    find_reports_by_video_id,
    list_recent_reports,
    read_metadata,
    read_report,
    update_metadata,
)
from services.transcript_guard import refresh_cooldown_remaining
from services.url_parser import YouTubeUrlError, extract_video_id


model_profiles = importlib.reload(_model_profiles)
DEFAULT_ANALYSIS_MODE = model_profiles.DEFAULT_ANALYSIS_MODE
MODE_NAMES = model_profiles.MODE_NAMES
MODEL_OPTIONS = model_profiles.MODEL_OPTIONS
REASONING_EFFORT_OPTIONS = model_profiles.REASONING_EFFORT_OPTIONS
get_default_profile = model_profiles.get_default_profile
get_analysis_mode = model_profiles.get_analysis_mode
is_high_cost_profile = model_profiles.is_high_cost_profile
resolve_model_profile = model_profiles.resolve_model_profile
mode_prompts = importlib.reload(_mode_prompts)
add_report_header = mode_prompts.add_report_header
build_mode_report_prompt = mode_prompts.build_mode_report_prompt
output_languages = importlib.reload(_output_languages)
DEFAULT_OUTPUT_LANGUAGE = output_languages.DEFAULT_OUTPUT_LANGUAGE
get_default_output_language = output_languages.get_default_output_language
get_output_language = output_languages.get_output_language
get_output_language_labels = output_languages.get_output_language_labels
openai_client = importlib.reload(_openai_client)
OpenAIRequestError = openai_client.OpenAIRequestError
generate_markdown_with_usage = openai_client.generate_markdown_with_usage
report_writer = importlib.reload(_report_writer)
save_report_with_metadata = report_writer.save_report_with_metadata
transcript_provider = importlib.reload(_transcript_provider)
TRANSLATION_TARGETS = transcript_provider.TRANSLATION_TARGETS
TranscriptError = transcript_provider.TranscriptError
fetch_transcript_result = transcript_provider.fetch_transcript_result
format_debug_exception = transcript_provider.format_debug_exception
transcribe_youtube_audio_result = transcript_provider.transcribe_youtube_audio_result
transcript_cache = importlib.reload(_transcript_cache)
read_transcript_cache = transcript_cache.read_transcript_cache
read_youtube_transcript_cache = transcript_cache.read_youtube_transcript_cache
write_transcript_cache = transcript_cache.write_transcript_cache
cost_estimator = importlib.reload(_cost_estimator)
estimate_report_cost = cost_estimator.estimate_report_cost
context_pack = importlib.reload(_context_pack)
build_context_pack = context_pack.build_context_pack
context_pack_exists = context_pack.context_pack_exists
save_context_pack = context_pack.save_context_pack


def configure_logging() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=LOGS_DIR / "app.log",
        level=logging.ERROR,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def show_debug_exception(exc: Exception) -> None:
    if show_debug_info:
        st.code(f"{type(exc).__name__}: {exc}")
        st.code("".join(traceback.format_exception(exc)))


def open_report(path: Path) -> None:
    st.session_state.selected_report_path = str(path)


def format_seconds(value: float | None) -> str:
    if value is None:
        return "unknown"
    minutes, seconds = divmod(int(value), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def prepared_from_cache(record) -> dict:
    return {
        "text": record.transcript_text,
        "source": record.source_type if record.source_type != "youtube" else "cached",
        "provider": record.transcript_provider or "cached",
        "language": record.transcript_language,
        "cache_path": record.transcript_cache_path,
        "created_at": record.created_at or record.fetched_at,
        "available_transcripts": list(record.available_transcripts),
        "debug_messages": [f"Loaded transcript from local cache: {record.transcript_cache_path}"],
    }


def prepared_from_result(result, *, source_url: str, source_type: str = "youtube") -> dict:
    available = [
        {
            "language": item.language,
            "language_code": item.language_code,
            "is_generated": item.is_generated,
            "is_translatable": item.is_translatable,
        }
        for item in result.available_transcripts
    ]
    cache_record = write_transcript_cache(
        source_id=result.video_id,
        video_id=result.video_id,
        source_url=source_url,
        source_type=source_type,
        transcript_text=result.text,
        transcript_language=result.requested_translation or result.selected_transcript.language_code,
        is_generated=result.selected_transcript.is_generated,
        available_transcripts=available,
        transcript_provider=result.transcript_provider,
    )
    return {
        "text": result.text,
        "source": source_type,
        "provider": result.transcript_provider,
        "language": cache_record.transcript_language,
        "cache_path": cache_record.transcript_cache_path,
        "created_at": cache_record.created_at or cache_record.fetched_at,
        "available_transcripts": available,
        "debug_messages": list(result.debug_messages) + [f"Saved transcript cache: {cache_record.transcript_cache_path}"],
    }


def prepared_from_manual(*, text: str, video_id: str, source_url: str, language: str) -> dict:
    source_id = video_id or source_url or "manual-transcript"
    cache_record = write_transcript_cache(
        source_id=source_id,
        video_id=video_id,
        source_url=source_url,
        source_type="manual",
        transcript_text=text,
        transcript_language=language,
        transcript_provider="manual",
    )
    return {
        "text": text,
        "source": "manual",
        "provider": "manual",
        "language": cache_record.transcript_language,
        "cache_path": cache_record.transcript_cache_path,
        "created_at": cache_record.created_at,
        "available_transcripts": [],
        "debug_messages": [f"Saved manual transcript cache: {cache_record.transcript_cache_path}"],
    }


def set_prepared_transcript(video_id: str, prepared: dict) -> None:
    st.session_state.prepared_video_id = video_id
    st.session_state.prepared_transcript = prepared
    st.session_state.transcript_debug_messages = prepared.get("debug_messages", [])


def can_refresh_youtube(video_id: str, cooldown_seconds: int = 60) -> tuple[bool, int]:
    last_by_video = st.session_state.get("last_youtube_fetch_at", {})
    remaining = refresh_cooldown_remaining(last_by_video.get(video_id), cooldown_seconds=cooldown_seconds)
    return remaining <= 0, remaining


def mark_youtube_fetch(video_id: str) -> None:
    last_by_video = dict(st.session_state.get("last_youtube_fetch_at", {}))
    last_by_video[video_id] = datetime.now().isoformat(timespec="seconds")
    st.session_state.last_youtube_fetch_at = last_by_video


def display_transcript_source(source: str) -> str:
    if source == "cached":
        return "cache"
    if source == "audio_transcription":
        return "audio"
    return source or "-"


def render_transcript_status_card(*, prepared: dict | None, transcript_error: str | None, cached_record=None) -> None:
    with st.container(border=True):
        st.subheader("Transcript Status")
        if prepared:
            status = "Ready"
        elif transcript_error:
            status = "Failed"
        else:
            status = "Not ready"

        col1, col2, col3 = st.columns(3)
        col1.metric("Status", status)
        col2.metric("Source", display_transcript_source((prepared or {}).get("source", "")))
        col3.metric("Characters", f"{len((prepared or {}).get('text', '')):,}")

        st.write(f"Provider: `{(prepared or {}).get('provider') or '-'}`")
        st.write(f"Language: `{(prepared or {}).get('language') or '-'}`")
        cache_path = (prepared or {}).get("cache_path") or getattr(cached_record, "transcript_cache_path", "")
        if cache_path:
            st.caption(f"Cache path: {cache_path}")
        if cached_record and not prepared:
            st.info("Cached transcript available. Use Load cached transcript to prepare it.")
        if transcript_error:
            st.warning(transcript_error)


def render_context_pack_controls(
    *,
    report_text: str,
    report_path: Path,
    metadata_path: Path | None,
    metadata: dict,
    transcript_excerpt: str = "",
    key_prefix: str,
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


def safe_metadata_for_display(value):
    if isinstance(value, dict):
        return {
            key: "[redacted]" if _looks_sensitive_key(key) else safe_metadata_for_display(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [safe_metadata_for_display(item) for item in value]
    return value


def _looks_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    sensitive_terms = ("api_key", "secret", "password", "authorization", "bearer", "credential")
    return any(term in normalized for term in sensitive_terms)


def _display_value(value) -> str:
    if value is None or value == "":
        return "-"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


def _metadata_value(metadata: dict, *keys: str) -> str:
    for key in keys:
        value = metadata.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def render_report_settings_summary(metadata: dict) -> None:
    st.caption("Report settings")
    summary_fields = [
        ("Analysis mode", _metadata_value(metadata, "analysis_mode", "report_type")),
        ("Report output language", _metadata_value(metadata, "output_language_label", "output_language")),
        ("Selected model", _metadata_value(metadata, "selected_model")),
        ("Reasoning effort", _metadata_value(metadata, "reasoning_effort")),
        ("Transcript source", display_transcript_source(_metadata_value(metadata, "transcript_source"))),
        ("Transcript language", _metadata_value(metadata, "transcript_language")),
        ("Generated", _metadata_value(metadata, "generated_at")),
    ]
    cols = st.columns(2)
    for index, (label, value) in enumerate(summary_fields):
        cols[index % 2].write(f"**{label}:** `{_display_value(value)}`")


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
    source = _metadata_value(metadata, "transcript_source")
    provider = _metadata_value(metadata, "transcript_provider")
    language = _metadata_value(metadata, "transcript_language")
    cache_path = _metadata_value(metadata, "transcript_cache_path")
    transcript_text, preview_source = _load_transcript_preview_text(metadata, transcript_excerpt)

    col1, col2, col3 = st.columns(3)
    col1.write(f"**Source:** `{_display_value(display_transcript_source(source))}`")
    col2.write(f"**Provider:** `{_display_value(provider)}`")
    col3.write(f"**Language:** `{_display_value(language)}`")
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
        )
    with transcript_tab:
        render_transcript_preview_tab(metadata=metadata, transcript_excerpt=transcript_excerpt)


configure_logging()
st.set_page_config(page_title="Info Catalyst", layout="wide")


st.title("Info Catalyst")
st.caption("Private MVP for turning YouTube transcripts into AI research reports.")

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

with st.sidebar:
    with st.expander("Debug options"):
        show_debug_info = st.checkbox("Show debug info", value=False)
        st.caption("Shows transcript diagnostics and exception tracebacks when errors occur.")
    st.subheader("Recent Reports")
    recent_reports = list_recent_reports(limit=20)
    if recent_reports:
        for index, record in enumerate(recent_reports):
            label = f"{record.display_title} ({record.generated_at[:16].replace('T', ' ')})"
            if st.button(label, key=f"recent-report-{index}", use_container_width=True):
                open_report(record.report_path)
    else:
        st.caption("No saved reports yet.")

selected_report_path = st.session_state.get("selected_report_path", "")
if selected_report_path:
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
        )
        st.divider()
    except Exception as exc:
        logging.exception("Failed to open archived report: %s", selected_report_path)
        st.error("Could not open that archived report.")
        show_debug_exception(exc)

transcript = ""
video_id = None
transcript_error = None
transcript_language = ""
duplicate_reports = []
cached_record = None

st.header("Step 1: Prepare Source")
youtube_url = st.text_input("YouTube URL", placeholder="https://www.youtube.com/watch?v=...")
video_title = st.text_input("Video title (optional)", placeholder="Optional title")

if youtube_url:
    try:
        video_id = extract_video_id(youtube_url)
        duplicate_reports = find_reports_by_video_id(video_id)
        if st.session_state.prepared_video_id != video_id:
            st.session_state.prepared_transcript = None
            st.session_state.prepared_video_id = video_id
            st.session_state.transcript_debug_messages = []

        cached_record = read_youtube_transcript_cache(video_id)
        if cached_record and not st.session_state.prepared_transcript:
            set_prepared_transcript(video_id, prepared_from_cache(cached_record))
            st.success("Loaded transcript from local cache.")
    except YouTubeUrlError as exc:
        logging.exception("Video URL parsing failed")
        transcript_error = str(exc)
        st.warning(transcript_error)
        show_debug_exception(exc)
    except Exception as exc:
        logging.exception("Unexpected transcript setup error")
        transcript_error = "Transcript extraction failed. You can paste a transcript manually to continue."
        st.session_state.transcript_debug_messages = [format_debug_exception(exc)]
        st.error(transcript_error)
        show_debug_exception(exc)

if video_id:
    st.caption(f"Parsed video ID: `{video_id}`")
else:
    st.caption("Parsed video ID: -")

prepared = st.session_state.get("prepared_transcript") or {}
if prepared:
    transcript = prepared.get("text", "")
    transcript_language = prepared.get("language", "")

col_a, col_b = st.columns(2)
with col_a:
    if st.button(
        "Load cached transcript",
        key=f"load-cache-{video_id or 'pending'}",
        disabled=not bool(video_id and cached_record),
        use_container_width=True,
    ):
        set_prepared_transcript(video_id, prepared_from_cache(cached_record))
        st.rerun()
with col_b:
    if st.button(
        "Fetch transcript from YouTube",
        key=f"fetch-youtube-{video_id or 'pending'}",
        disabled=not bool(video_id),
        use_container_width=True,
    ):
        refresh_ok, remaining = can_refresh_youtube(video_id)
        if not refresh_ok:
            st.warning(f"Please wait {remaining} seconds before fetching this transcript from YouTube again.")
        else:
            mark_youtube_fetch(video_id)
            try:
                with st.spinner("Fetching transcript from YouTube..."):
                    transcript_result = fetch_transcript_result(video_id)
                set_prepared_transcript(
                    video_id,
                    prepared_from_result(transcript_result, source_url=youtube_url, source_type="youtube"),
                )
                st.success("Transcript fetched from YouTube and saved to local cache.")
                st.rerun()
            except TranscriptError as exc:
                logging.exception("YouTube transcript fetch failed")
                transcript_error = str(exc)
                st.session_state.transcript_debug_messages = list(getattr(exc, "debug_messages", ()))
                st.warning(transcript_error)
                show_debug_exception(exc)

with st.expander("Advanced transcript controls"):
    st.caption("Use refresh only when you need to replace the prepared or cached transcript. Cooldown still applies.")
    if st.button(
        "Refresh transcript from YouTube",
        key=f"refresh-youtube-{video_id or 'pending'}",
        disabled=not bool(video_id),
        use_container_width=True,
    ):
        refresh_ok, remaining = can_refresh_youtube(video_id)
        if not refresh_ok:
            st.warning(f"Please wait {remaining} seconds before refreshing this transcript from YouTube again.")
        else:
            mark_youtube_fetch(video_id)
            try:
                with st.spinner("Refreshing transcript from YouTube..."):
                    transcript_result = fetch_transcript_result(video_id)
                set_prepared_transcript(
                    video_id,
                    prepared_from_result(transcript_result, source_url=youtube_url, source_type="youtube"),
                )
                st.success("Transcript refreshed from YouTube and saved to local cache.")
                st.rerun()
            except TranscriptError as exc:
                logging.exception("YouTube transcript refresh failed")
                transcript_error = str(exc)
                st.session_state.transcript_debug_messages = list(getattr(exc, "debug_messages", ()))
                st.warning(transcript_error)
                show_debug_exception(exc)

prepared = st.session_state.get("prepared_transcript") or {}
render_transcript_status_card(prepared=prepared, transcript_error=transcript_error, cached_record=cached_record)

available = prepared.get("available_transcripts") or []
if available:
    st.caption(
        "Available transcript languages: "
        + ", ".join(
            f"{item.get('language_code', '')} - {item.get('language', '')}".strip(" -")
            for item in available
        )
    )

if youtube_url and show_debug_info:
    debug_messages = st.session_state.get("transcript_debug_messages", [])
    with st.expander("Debug options"):
        st.code(f"parsed video ID: {video_id}")
        prepared = st.session_state.get("prepared_transcript") or {}
        st.code(f"transcript source: {prepared.get('source', '')}")
        st.code(f"cache path: {prepared.get('cache_path', '')}")
        if debug_messages:
            for message in debug_messages:
                st.code(message)
        else:
            st.caption("No transcript debug messages captured for the current source.")

generate_duplicate_report = True
if video_id and duplicate_reports:
    latest_duplicate = duplicate_reports[0]
    st.warning("This video was analyzed before.")
    duplicate_choice = st.radio(
        "Choose how to continue",
        ["Open latest existing report", "Generate a new report anyway"],
        horizontal=True,
    )
    generate_duplicate_report = duplicate_choice == "Generate a new report anyway"
    if duplicate_choice == "Open latest existing report":
        if st.button("Open latest existing report", use_container_width=False):
            open_report(latest_duplicate.report_path)
            st.rerun()

show_other_options = not bool(transcript)
with st.expander("Other transcript options", expanded=show_other_options):
    if transcript:
        st.caption("Paste a transcript here if you need to replace the prepared transcript.")
    else:
        st.caption("Use this when the cached or YouTube transcript is unavailable, or when you want to provide your own transcript.")

    manual_transcript = st.text_area(
        "Manual transcript fallback",
        value="",
        height=220,
        placeholder="Paste the transcript here if automatic extraction fails.",
    )
    manual_language = st.selectbox(
        "Manual transcript language",
        ["zh-TW", "zh-Hant", "zh-Hans", "en", "manual"],
        index=0,
    )
    if manual_transcript.strip():
        if st.button("Save manual transcript to cache", key=f"save-manual-{video_id or 'manual'}"):
            prepared = prepared_from_manual(
                text=manual_transcript.strip(),
                video_id=video_id or "",
                source_url=youtube_url,
                language=manual_language,
            )
            set_prepared_transcript(video_id or "manual-transcript", prepared)
            st.success("Manual transcript saved to local cache.")
            st.rerun()

with st.expander("Audio transcription fallback"):
    if not video_id:
        st.caption("Audio transcription fallback requires a valid YouTube URL.")
    else:
        st.warning(
            "Audio transcription may take longer than YouTube transcript extraction and may use additional OpenAI API cost. "
            "Use it only when YouTube transcript extraction is blocked or unavailable and you have the right to process the audio."
        )
        st.caption(f"Transcription model: `{transcript_provider.OPENAI_TRANSCRIPTION_MODEL}`")
        st.caption("Duration and file size are checked during audio download when this fallback is started.")
        audio_confirm = st.checkbox(
            "I understand audio transcription may take longer and use additional API cost.",
            key=f"audio-confirm-{video_id}",
        )
        if st.button("Use audio transcription fallback", disabled=not audio_confirm, key=f"audio-fallback-{video_id}"):
            try:
                with st.spinner("Downloading audio and transcribing..."):
                    transcript_result = transcribe_youtube_audio_result(video_id)
                set_prepared_transcript(
                    video_id,
                    prepared_from_result(transcript_result, source_url=youtube_url, source_type="audio_transcription"),
                )
                st.success("Audio transcription completed and saved to local cache.")
                st.rerun()
            except TranscriptError as exc:
                logging.exception("Audio transcription fallback failed")
                st.session_state.transcript_debug_messages = list(getattr(exc, "debug_messages", ()))
                st.error(str(exc))
                show_debug_exception(exc)
            except Exception as exc:
                logging.exception("Audio transcription fallback failed")
                st.session_state.transcript_debug_messages = [format_debug_exception(exc)]
                st.error("Audio transcription fallback failed. Check debug info or paste the transcript manually.")
                show_debug_exception(exc)

prepared = st.session_state.get("prepared_transcript") or {}
final_transcript = prepared.get("text", "")
if final_transcript and not transcript_language:
    transcript_language = prepared.get("language", "")

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
    st.info("Paste a transcript in Other transcript options to continue.")

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

if generate:
    try:
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
        )
    except OpenAIRequestError as exc:
        logging.exception("Report generation failed")
        st.error(str(exc))
        show_debug_exception(exc)
    except Exception as exc:
        logging.exception("Report generation failed")
        st.error("Report generation failed. Please check your API key, model setting, or transcript input and try again.")
        show_debug_exception(exc)
