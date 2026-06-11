import json
import shutil
import uuid
from pathlib import Path

from services.transcript_cache import (
    cache_path_for_youtube,
    read_youtube_transcript_cache,
    write_transcript_cache,
)


def test_transcript_cache_write_and_read_for_youtube():
    workspace = _workspace_tmp_dir()
    try:
        record = write_transcript_cache(
            source_id="abc12345678",
            video_id="abc12345678",
            source_url="https://youtu.be/abc12345678",
            source_type="youtube",
            transcript_text="逐字稿內容",
            transcript_language="zh-Hant",
            is_generated=False,
            transcript_provider="youtube_transcript_api",
            available_transcripts=({"language_code": "zh-Hant", "language": "Chinese"},),
            transcripts_dir=workspace,
        )

        assert record.transcript_cache_path == str(workspace / "abc12345678.json")
        loaded = read_youtube_transcript_cache("abc12345678", transcripts_dir=workspace)

        assert loaded is not None
        assert loaded.transcript_text == "逐字稿內容"
        assert loaded.source_type == "youtube"
        assert loaded.transcript_provider == "youtube_transcript_api"
        assert loaded.available_transcripts[0]["language_code"] == "zh-Hant"
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def test_cache_path_for_youtube_is_video_id_json():
    path = cache_path_for_youtube("abc12345678", transcripts_dir=Path("reports") / "transcripts")

    assert path.as_posix().endswith("reports/transcripts/abc12345678.json")


def test_manual_transcript_cache_save_records_manual_source():
    workspace = _workspace_tmp_dir()
    try:
        record = write_transcript_cache(
            source_id="manual-transcript",
            source_type="manual",
            transcript_text="manual body",
            transcript_language="zh-TW",
            transcript_provider="manual",
            transcripts_dir=workspace,
        )
        payload = json.loads(Path(record.transcript_cache_path).read_text(encoding="utf-8"))

        assert payload["source_type"] == "manual"
        assert payload["transcript_provider"] == "manual"
        assert payload["created_at"]
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def _workspace_tmp_dir() -> Path:
    path = Path("tests") / ".tmp" / f"transcript-cache-{uuid.uuid4().hex}"
    path.mkdir(parents=True)
    return path
