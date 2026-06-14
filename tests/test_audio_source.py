import shutil
import uuid
from pathlib import Path

import pytest

from services.transcript_cache import cache_path_for_source
from services import audio_source
from services.audio_source import (
    AudioSourceError,
    build_audio_source_id,
    download_audio_url,
    is_supported_audio_url,
    load_cached_audio_transcript,
    transcribe_audio_url,
)
from services.transcript_cache import write_transcript_cache


@pytest.fixture
def workspace(monkeypatch):
    path = Path("tests") / ".tmp" / f"audio-source-{uuid.uuid4().hex}"
    path.mkdir(parents=True)
    monkeypatch.setattr(audio_source, "AUDIO_CACHE_DIR", path / "reports" / "audio-cache")
    monkeypatch.setattr("services.transcript_cache.TRANSCRIPTS_DIR", path / "reports" / "transcripts")
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_build_audio_source_id_is_stable_and_filename_safe():
    first = build_audio_source_id("https://example.com/podcast/episode.mp3?token=abc")
    second = build_audio_source_id("https://example.com/podcast/episode.mp3?token=abc")

    assert first == second
    assert first.startswith("audio-")
    assert all(char.isalnum() or char in {"-", "_"} for char in first)
    assert len(first) < 40


@pytest.mark.parametrize(
    "url",
    [
        "",
        "file:///tmp/audio.mp3",
        "C:/tmp/audio.mp3",
        "ftp://example.com/audio.mp3",
        "http://localhost/audio.mp3",
        "http://127.0.0.1/audio.mp3",
        "http://10.0.0.5/audio.mp3",
        "https://example.com/podcast-page",
    ],
)
def test_unsupported_audio_urls_are_rejected(url):
    assert not is_supported_audio_url(url)


def test_supported_audio_url_accepts_direct_audio_extension():
    assert is_supported_audio_url("https://cdn.example.com/show/episode.m4a")


def test_download_audio_url_streams_supported_audio(monkeypatch, workspace):
    monkeypatch.setattr(
        audio_source.requests,
        "get",
        lambda *args, **kwargs: FakeResponse(
            headers={"Content-Type": "audio/mpeg", "Content-Length": "6"},
            chunks=[b"abc", b"def"],
        ),
    )

    path = download_audio_url("https://cdn.example.com/episode.mp3", source_id="audio-test")

    assert path.read_bytes() == b"abcdef"


def test_download_audio_url_rejects_non_audio_response(monkeypatch, workspace):
    monkeypatch.setattr(
        audio_source.requests,
        "get",
        lambda *args, **kwargs: FakeResponse(headers={"Content-Type": "text/html"}, chunks=[b"<html>"]),
    )

    with pytest.raises(AudioSourceError, match="supported audio"):
        download_audio_url("https://example.com/episode.mp3", source_id="audio-test")


def test_download_audio_url_enforces_size_limit_from_header(monkeypatch, workspace):
    monkeypatch.setattr(audio_source, "MAX_AUDIO_BYTES", 5)
    monkeypatch.setattr(
        audio_source.requests,
        "get",
        lambda *args, **kwargs: FakeResponse(
            headers={"Content-Type": "audio/mpeg", "Content-Length": "6"},
            chunks=[b"abcdef"],
        ),
    )

    with pytest.raises(AudioSourceError, match="too large"):
        download_audio_url("https://cdn.example.com/episode.mp3", source_id="audio-test")


def test_transcribe_audio_url_uses_mocked_openai_and_writes_cache(monkeypatch, workspace):
    transcripts_dir = workspace / "reports" / "transcripts"
    monkeypatch.setattr(
        audio_source,
        "download_audio_url",
        lambda url, source_id: _write_audio_file(workspace / "episode.mp3"),
    )
    monkeypatch.setattr(
        audio_source,
        "transcribe_audio_file",
        lambda audio_path, language="", debug_messages=None: "mock transcript",
    )
    monkeypatch.setattr(
        audio_source,
        "write_transcript_cache",
        lambda **kwargs: write_transcript_cache(**kwargs, transcripts_dir=transcripts_dir),
    )

    result = transcribe_audio_url(
        "https://cdn.example.com/podcast/episode.mp3",
        source_title="Episode 1",
        language_hint="en",
    )
    cached = audio_source.read_transcript_cache(Path(result.cache_path))

    assert result.source_id.startswith("audio-")
    assert result.source_title == "Episode 1"
    assert result.transcript_text == "mock transcript"
    assert result.transcript_language == "en"
    assert result.transcript_provider == "openai_transcription"
    assert cached.source_type == "podcast_audio_url"
    assert cached.source_url == "https://cdn.example.com/podcast/episode.mp3"
    assert cached.video_id == ""
    assert cached.is_generated is True
    assert not (workspace / "episode.mp3").exists()


def test_cached_audio_transcript_can_be_loaded_by_source_id(monkeypatch, workspace):
    source_id = "audio-cachecase"
    transcripts_dir = workspace / "reports" / "transcripts"
    monkeypatch.setattr(
        audio_source,
        "cache_path_for_source",
        lambda source_id: cache_path_for_source(source_id, transcripts_dir),
    )
    record = write_transcript_cache(
        source_id=source_id,
        source_type="podcast_audio_url",
        source_url="https://cdn.example.com/cache.mp3",
        transcript_text="cached text",
        transcript_language="zh",
        transcript_provider="openai_transcription",
        transcripts_dir=transcripts_dir,
    )

    loaded = load_cached_audio_transcript(record.source_id)

    assert loaded.transcript_text == "cached text"
    assert loaded.source_type == "podcast_audio_url"


class FakeResponse:
    def __init__(self, *, headers, chunks, status_code=200):
        self.headers = headers
        self._chunks = chunks
        self.status_code = status_code

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def iter_content(self, chunk_size):
        yield from self._chunks


def _write_audio_file(path: Path) -> Path:
    path.write_bytes(b"audio")
    return path
