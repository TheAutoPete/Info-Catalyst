import json
import os
import shutil
import uuid
from pathlib import Path

from services.transcript_provider import (
    TranscriptError,
    _metadata_from_ytdlp_path,
    _parse_ytdlp_json3,
    _select_transcript,
    _sort_transcript_items,
    _transcript_time_range,
    _without_proxy_environment,
    _youtube_http_client,
    fetch_transcript_result,
)


class FakeTranscript:
    def __init__(self, language_code, is_generated=False):
        self.language_code = language_code
        self.language = language_code
        self.is_generated = is_generated
        self.is_translatable = False
        self.translation_languages = []


class FakeTranscriptList:
    def __init__(self, transcripts, selected=None):
        self.transcripts = transcripts
        self.selected = selected

    def __iter__(self):
        return iter(self.transcripts)


def test_select_transcript_uses_language_priority():
    preferred = FakeTranscript("zh-TW")
    transcript_list = FakeTranscriptList(
        [FakeTranscript("en"), preferred],
    )

    assert _select_transcript(transcript_list, tuple(transcript_list)) is preferred


def test_select_transcript_prefers_manual_transcripts():
    generated_preferred = FakeTranscript("zh-TW", is_generated=True)
    manual_available = FakeTranscript("en")
    transcript_list = FakeTranscriptList([generated_preferred, manual_available])

    assert _select_transcript(transcript_list, tuple(transcript_list)) is manual_available


def test_select_transcript_uses_generated_preferred_language_when_no_manual_match():
    generated_preferred = FakeTranscript("zh-TW", is_generated=True)
    transcript_list = FakeTranscriptList([FakeTranscript("fr"), generated_preferred])

    assert _select_transcript(transcript_list, tuple(transcript_list)) is generated_preferred


def test_select_transcript_uses_chinese_language_priority():
    preferred = FakeTranscript("zh-Hans")
    transcript_list = FakeTranscriptList([FakeTranscript("zh-CN"), preferred, FakeTranscript("en")])

    assert _select_transcript(transcript_list, tuple(transcript_list)) is preferred


def test_select_transcript_falls_back_to_first_available():
    first_available = FakeTranscript("fr")
    transcript_list = FakeTranscriptList([first_available, FakeTranscript("de")])

    assert _select_transcript(transcript_list, tuple(transcript_list)) is first_available


def test_youtube_http_client_ignores_environment_proxies():
    assert _youtube_http_client().trust_env is False


def test_sort_transcript_items_uses_start_time():
    items = [
        {"text": "later", "start": 20.0, "duration": 2.0},
        {"text": "earlier", "start": 1.0, "duration": 3.0},
    ]

    assert [item["text"] for item in _sort_transcript_items(items)] == ["earlier", "later"]


def test_transcript_time_range_uses_start_and_duration():
    items = [
        {"text": "first", "start": 1.0, "duration": 3.0},
        {"text": "last", "start": 20.0, "duration": 2.5},
    ]

    assert _transcript_time_range(items) == (1.0, 22.5)


def test_parse_ytdlp_json3_extracts_text_and_timing():
    workspace = Path("tests") / ".tmp" / f"json3-{uuid.uuid4().hex}"
    path = workspace / "video.zh-Hant.json3"
    path.parent.mkdir(parents=True)
    try:
        path.write_text(
            json.dumps(
                {
                    "events": [
                        {"tStartMs": 1000, "dDurationMs": 2500, "segs": [{"utf8": "第一段"}, {"utf8": "文字"}]},
                        {"tStartMs": 4000, "dDurationMs": 1000, "segs": [{"utf8": "第二段"}]},
                        {"tStartMs": 5000, "segs": [{"utf8": "   "}]},
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        items = _parse_ytdlp_json3(path)

        assert items == (
            {"text": "第一段文字", "start": 1.0, "duration": 2.5},
            {"text": "第二段", "start": 4.0, "duration": 1.0},
        )
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def test_metadata_from_ytdlp_path_uses_language_suffix():
    metadata = _metadata_from_ytdlp_path(Path("video.zh-Hant.json3"))

    assert metadata.language_code == "zh-Hant"


def test_without_proxy_environment_temporarily_clears_proxy_vars():
    os.environ["HTTP_PROXY"] = "http://127.0.0.1:9"

    with _without_proxy_environment():
        assert "HTTP_PROXY" not in os.environ

    assert os.environ["HTTP_PROXY"] == "http://127.0.0.1:9"


def test_fetch_transcript_result_does_not_auto_transcribe_audio(monkeypatch):
    class BrokenApi:
        def list(self, video_id):
            raise RuntimeError("blocked")

    monkeypatch.setattr("services.transcript_provider._youtube_transcript_api", lambda: BrokenApi())

    try:
        fetch_transcript_result("abc12345678")
    except TranscriptError as exc:
        assert "Transcript extraction failed" in str(exc)
    else:
        raise AssertionError("expected TranscriptError")
