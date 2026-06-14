import logging
import hashlib
from datetime import datetime

import streamlit as st

from services import transcript_provider
from services.report_archive import find_reports_by_video_id
from services.transcript_cache import read_youtube_transcript_cache, write_transcript_cache
from services.transcript_guard import refresh_cooldown_remaining
from services.transcript_provider import (
    TranscriptError,
    fetch_transcript_result,
    format_debug_exception,
    transcribe_youtube_audio_result,
)
from services.url_parser import YouTubeUrlError, extract_video_id
from ui.components import render_transcript_status_card


SOURCE_TYPE_YOUTUBE_LABEL = "YouTube URL"
SOURCE_TYPE_MANUAL_TEXT_LABEL = "Manual Text / Article Paste"
MANUAL_SOURCE_LANGUAGES = ["zh-TW", "zh-Hant", "zh-Hans", "en", "ja", "unknown"]


def stable_manual_source_id(*, source_title: str, source_url: str, text: str) -> str:
    seed = source_url.strip() or f"{source_title.strip()}:{text.strip()[:500]}"
    if not seed.strip():
        return "manual-text"
    return f"manual-{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:16]}"


def prepared_from_manual_text(
    *,
    text: str,
    source_title: str,
    source_url: str,
    language: str,
    source_id: str,
) -> dict:
    return {
        "text": text,
        "source": "manual_text",
        "provider": "manual_text",
        "language": language,
        "source_type": "manual_text",
        "source_title": source_title,
        "source_url": source_url,
        "source_id": source_id,
        "cache_path": "",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "available_transcripts": [],
        "debug_messages": [],
    }


def prepared_from_cache(record) -> dict:
    return {
        "text": record.transcript_text,
        "source": record.source_type if record.source_type != "youtube" else "cached",
        "provider": record.transcript_provider or "cached",
        "language": record.transcript_language,
        "source_type": record.source_type,
        "source_id": record.source_id,
        "source_url": record.source_url,
        "source_title": "",
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
        "source_type": source_type,
        "source_id": result.video_id,
        "source_url": source_url,
        "source_title": "",
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
        "source_type": "youtube",
        "source_id": video_id or source_id,
        "source_url": source_url,
        "source_title": "",
        "cache_path": cache_record.transcript_cache_path,
        "created_at": cache_record.created_at,
        "available_transcripts": [],
        "debug_messages": [f"Saved manual transcript cache: {cache_record.transcript_cache_path}"],
    }


def set_prepared_transcript(video_id: str, prepared: dict) -> None:
    st.session_state.prepared_video_id = video_id
    st.session_state.prepared_source_id = prepared.get("source_id") or video_id
    st.session_state.prepared_source_type = prepared.get("source_type") or "youtube"
    st.session_state.prepared_transcript = prepared
    st.session_state.transcript_debug_messages = prepared.get("debug_messages", [])


def clear_prepared_transcript() -> None:
    st.session_state.prepared_video_id = ""
    st.session_state.prepared_source_id = ""
    st.session_state.prepared_source_type = ""
    st.session_state.prepared_transcript = None
    st.session_state.transcript_debug_messages = []


def reset_prepared_transcript_for_source_type(source_type: str) -> None:
    if st.session_state.get("active_source_type") == source_type:
        return
    st.session_state.active_source_type = source_type
    clear_prepared_transcript()


def can_refresh_youtube(video_id: str, cooldown_seconds: int = 60) -> tuple[bool, int]:
    last_by_video = st.session_state.get("last_youtube_fetch_at", {})
    remaining = refresh_cooldown_remaining(last_by_video.get(video_id), cooldown_seconds=cooldown_seconds)
    return remaining <= 0, remaining


def mark_youtube_fetch(video_id: str) -> None:
    last_by_video = dict(st.session_state.get("last_youtube_fetch_at", {}))
    last_by_video[video_id] = datetime.now().isoformat(timespec="seconds")
    st.session_state.last_youtube_fetch_at = last_by_video


def render_transcript_fetch_controls(
    *,
    video_id: str | None,
    youtube_url: str,
    cached_record,
    show_debug_exception,
) -> str | None:
    transcript_error = None
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
    return transcript_error


def render_advanced_transcript_controls(
    *,
    video_id: str | None,
    youtube_url: str,
    show_debug_exception,
) -> str | None:
    transcript_error = None
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
    return transcript_error


def render_transcript_debug(*, youtube_url: str, video_id: str | None, show_debug: bool) -> None:
    if not (youtube_url and show_debug):
        return

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


def render_duplicate_report_notice(*, video_id: str | None, duplicate_reports: list, open_report) -> bool:
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
    return generate_duplicate_report


def render_manual_transcript_fallback(
    *,
    transcript: str,
    video_id: str | None,
    youtube_url: str,
) -> None:
    show_other_options = not bool(transcript)
    with st.expander("Other transcript options", expanded=show_other_options):
        if transcript:
            st.caption("Paste a transcript here if you need to replace the prepared transcript.")
        else:
            st.caption(
                "Use this when the cached or YouTube transcript is unavailable, or when you want to provide your own transcript."
            )

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


def render_audio_fallback_controls(*, video_id: str | None, youtube_url: str, show_debug_exception) -> None:
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
                        prepared_from_result(
                            transcript_result,
                            source_url=youtube_url,
                            source_type="audio_transcription",
                        ),
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


def render_transcript_preview(*, final_transcript: str, source_url: str, transcript_error: str | None) -> None:
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
    elif source_url and transcript_error:
        st.info("Paste a transcript in Other transcript options to continue.")


def render_manual_text_source_controls() -> dict:
    source_title = st.text_input("Source title", placeholder="Article, transcript, notes, or copied content title")
    source_url = st.text_input("Source URL (optional)", placeholder="https://example.com/source")
    source_language = st.selectbox("Source language", MANUAL_SOURCE_LANGUAGES, index=0)
    manual_text = st.text_area(
        "Pasted article text / transcript / notes / copied content",
        height=300,
        placeholder="Paste the source text you want Info Catalyst to analyze.",
    )
    source_id = stable_manual_source_id(source_title=source_title, source_url=source_url, text=manual_text)

    if st.button(
        "Prepare manual text source",
        disabled=not bool(source_title.strip() and manual_text.strip()),
        use_container_width=True,
    ):
        prepared = prepared_from_manual_text(
            text=manual_text.strip(),
            source_title=source_title.strip(),
            source_url=source_url.strip(),
            language=source_language,
            source_id=source_id,
        )
        set_prepared_transcript(source_id, prepared)
        st.success("Manual text source prepared.")
        st.rerun()

    return {
        "source_title": source_title,
        "source_url": source_url,
        "source_language": source_language,
        "source_id": source_id,
    }


def render_youtube_source_section(*, show_debug: bool, open_report, show_debug_exception) -> dict:
    transcript = ""
    video_id = None
    transcript_error = None
    transcript_language = ""
    duplicate_reports = []
    cached_record = None

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

    fetch_error = render_transcript_fetch_controls(
        video_id=video_id,
        youtube_url=youtube_url,
        cached_record=cached_record,
        show_debug_exception=show_debug_exception,
    )
    transcript_error = fetch_error or transcript_error

    refresh_error = render_advanced_transcript_controls(
        video_id=video_id,
        youtube_url=youtube_url,
        show_debug_exception=show_debug_exception,
    )
    transcript_error = refresh_error or transcript_error

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

    render_transcript_debug(youtube_url=youtube_url, video_id=video_id, show_debug=show_debug)
    generate_duplicate_report = render_duplicate_report_notice(
        video_id=video_id,
        duplicate_reports=duplicate_reports,
        open_report=open_report,
    )

    render_manual_transcript_fallback(transcript=transcript, video_id=video_id, youtube_url=youtube_url)
    render_audio_fallback_controls(video_id=video_id, youtube_url=youtube_url, show_debug_exception=show_debug_exception)

    prepared = st.session_state.get("prepared_transcript") or {}
    final_transcript = prepared.get("text", "")
    if final_transcript and not transcript_language:
        transcript_language = prepared.get("language", "")

    render_transcript_preview(
        final_transcript=final_transcript,
        source_url=youtube_url,
        transcript_error=transcript_error,
    )

    return {
        "youtube_url": youtube_url,
        "video_title": video_title,
        "video_id": video_id,
        "source_type": "youtube",
        "source_title": video_title,
        "source_url": youtube_url,
        "source_id": video_id or "",
        "transcript_language": transcript_language,
        "duplicate_reports": duplicate_reports,
        "generate_duplicate_report": generate_duplicate_report,
        "final_transcript": final_transcript,
    }


def render_manual_text_source_section() -> dict:
    manual_state = render_manual_text_source_controls()
    prepared = st.session_state.get("prepared_transcript") or {}
    if prepared.get("source_type") != "manual_text":
        prepared = {}
    final_transcript = prepared.get("text", "")
    transcript_language = prepared.get("language") or manual_state["source_language"]
    source_title = prepared.get("source_title") or manual_state["source_title"]
    source_url = prepared.get("source_url") or manual_state["source_url"]
    source_id = prepared.get("source_id") or manual_state["source_id"]

    render_transcript_status_card(prepared=prepared, transcript_error=None, cached_record=None)
    render_transcript_preview(
        final_transcript=final_transcript,
        source_url=source_url,
        transcript_error=None,
    )

    return {
        "youtube_url": "",
        "video_title": source_title,
        "video_id": "",
        "source_type": "manual_text",
        "source_title": source_title,
        "source_url": source_url,
        "source_id": source_id,
        "transcript_language": transcript_language,
        "duplicate_reports": [],
        "generate_duplicate_report": True,
        "final_transcript": final_transcript,
    }


def render_prepare_source_section(*, show_debug: bool, open_report, show_debug_exception) -> dict:
    st.header("Step 1: Prepare Source")
    selected_label = st.selectbox(
        "Source Type",
        [SOURCE_TYPE_YOUTUBE_LABEL, SOURCE_TYPE_MANUAL_TEXT_LABEL],
        key="source_type_selector",
    )
    source_type = "manual_text" if selected_label == SOURCE_TYPE_MANUAL_TEXT_LABEL else "youtube"
    reset_prepared_transcript_for_source_type(source_type)

    if source_type == "manual_text":
        return render_manual_text_source_section()

    return render_youtube_source_section(
        show_debug=show_debug,
        open_report=open_report,
        show_debug_exception=show_debug_exception,
    )
