from datetime import datetime


def refresh_cooldown_remaining(
    last_fetch_iso: str | None,
    *,
    now: datetime | None = None,
    cooldown_seconds: int = 60,
) -> int:
    if not last_fetch_iso:
        return 0
    now = now or datetime.now()
    try:
        last_fetch = datetime.fromisoformat(last_fetch_iso)
    except ValueError:
        return 0
    elapsed = int((now - last_fetch).total_seconds())
    return max(0, cooldown_seconds - elapsed)
