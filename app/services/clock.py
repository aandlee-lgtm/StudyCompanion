"""'Today' in the student's timezone. Tests can freeze the date with ``set_today``."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

_override: date | None = None
_timezone = "Australia/Sydney"


def set_timezone(tz: str | None) -> None:
    """Called at startup and when Settings change, so timestamps use the student's local time."""
    global _timezone
    if tz:
        try:
            ZoneInfo(tz)
            _timezone = tz
        except Exception:
            pass


def local_now() -> datetime:
    """Naive local wall-clock time in the student's timezone (what the database stores).

    When tests freeze the date with set_today, the date part follows the frozen date."""
    try:
        now = datetime.now(ZoneInfo(_timezone)).replace(tzinfo=None)
    except Exception:
        now = datetime.now()
    if _override is not None:
        now = datetime.combine(_override, now.time())
    return now


def set_today(d: date | None) -> None:
    global _override
    _override = d


def today(tz: str | None = None) -> date:
    if _override is not None:
        return _override
    try:
        return datetime.now(ZoneInfo(tz or _timezone)).date()
    except Exception:
        return date.today()


def weekdays_between(start: date, end: date, weekdays: list[int]) -> list[date]:
    """Study days strictly after ``start`` and strictly before ``end``."""
    out, d = [], start + timedelta(days=1)
    while d < end:
        if d.weekday() in weekdays:
            out.append(d)
        d += timedelta(days=1)
    return out
