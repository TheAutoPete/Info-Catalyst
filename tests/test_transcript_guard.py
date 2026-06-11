from datetime import datetime, timedelta

from services.transcript_guard import refresh_cooldown_remaining


def test_refresh_cooldown_allows_empty_or_invalid_timestamp():
    assert refresh_cooldown_remaining(None) == 0
    assert refresh_cooldown_remaining("not-a-date") == 0


def test_refresh_cooldown_blocks_recent_fetch():
    now = datetime(2026, 6, 12, 8, 0, 0)
    last_fetch = (now - timedelta(seconds=20)).isoformat(timespec="seconds")

    assert refresh_cooldown_remaining(last_fetch, now=now, cooldown_seconds=60) == 40


def test_refresh_cooldown_allows_after_window():
    now = datetime(2026, 6, 12, 8, 0, 0)
    last_fetch = (now - timedelta(seconds=61)).isoformat(timespec="seconds")

    assert refresh_cooldown_remaining(last_fetch, now=now, cooldown_seconds=60) == 0
