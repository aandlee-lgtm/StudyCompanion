"""'Today' in the student's timezone. Tests can freeze the date with ``set_today``."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

_override: date | None = None


def set_today(d: date | None) -> None:
    global _override
    _override = d


def today(tz: str = "Australia/Sydney") -> date:
    if _override is not None:
        return _override
    try:
        return datetime.now(ZoneInfo(tz)).date()
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
