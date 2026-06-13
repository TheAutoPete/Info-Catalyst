import streamlit as st


def display_transcript_source(source: str) -> str:
    if source == "cached":
        return "cache"
    if source == "audio_transcription":
        return "audio"
    return source or "-"


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


def display_value(value) -> str:
    if value is None or value == "":
        return "-"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


def metadata_value(metadata: dict, *keys: str) -> str:
    for key in keys:
        value = metadata.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


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
