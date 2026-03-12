"""Production calendar: local JSON storage. Manual update or default 21*8h per month."""
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

from config import PROD_CALENDAR_PATH

TZ = ZoneInfo("Europe/Moscow")

# Structure: {"dates": {"2025-03-01": {"is_working": true, "work_hours": 8, "month_norm_hours": 168}, ...}}
_CALENDAR: dict = {}


def _load_calendar():
    global _CALENDAR
    if _CALENDAR and "dates" in _CALENDAR:
        return
    PROD_CALENDAR_PATH.parent.mkdir(parents=True, exist_ok=True)
    if PROD_CALENDAR_PATH.exists():
        try:
            with open(PROD_CALENDAR_PATH, "r", encoding="utf-8") as f:
                _CALENDAR = json.load(f)
        except (json.JSONDecodeError, IOError):
            _CALENDAR = {"dates": {}}
    else:
        _CALENDAR = {"dates": {}}


def _save_calendar():
    PROD_CALENDAR_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PROD_CALENDAR_PATH, "w", encoding="utf-8") as f:
        json.dump(_CALENDAR, f, ensure_ascii=False, indent=2)


def _generate_default_month(year: int, month: int) -> dict:
    """Generate default: 21 working days * 8h = 168h per month."""
    from calendar import monthrange
    _, last_day = monthrange(year, month)
    month_norm = 21 * 8
    result = {}
    for d in range(1, last_day + 1):
        dt = datetime(year, month, d)
        # Simple weekend: Sat=5, Sun=6
        wd = dt.weekday()
        is_working = wd < 5
        work_hours = 8 if is_working else 0
        date_str = f"{year}-{month:02d}-{d:02d}"
        result[date_str] = {
            "is_working": is_working,
            "work_hours": work_hours,
            "month_norm_hours": month_norm,
        }
    return result


def ensure_prod_calendar_updated():
    """Ensure current and next month exist in calendar (default values)."""
    _load_calendar()
    now = datetime.now(TZ)
    year, month = now.year, now.month
    updated = False
    for ym in [(year, month), (year if month < 12 else year + 1, 1 if month == 12 else month + 1)]:
        y, m = ym
        prefix = f"{y}-{m:02d}-"
        has_any = any(k.startswith(prefix) for k in _CALENDAR.get("dates", {}))
        if not has_any:
            gen = _generate_default_month(y, m)
            _CALENDAR.setdefault("dates", {}).update(gen)
            updated = True
    if updated:
        _save_calendar()


def get_month_norm_hours_for_date(date_str: str, session=None) -> float:
    """Return month norm hours for the month of date_str. Fallback: 8*21."""
    _load_calendar()
    work_hours_norm = 8 * 21
    prefix = ""
    try:
        parts = date_str[:10].split("-")
        if len(parts) < 2:
            return work_hours_norm
        year, month = int(parts[0]), int(parts[1])
        prefix = f"{year}-{month:02d}-"
        for k, v in _CALENDAR.get("dates", {}).items():
            if k.startswith(prefix) and v.get("month_norm_hours"):
                return float(v["month_norm_hours"])
    except (ValueError, IndexError):
        return work_hours_norm
    ensure_prod_calendar_updated()
    for k, v in _CALENDAR.get("dates", {}).items():
        if k.startswith(prefix):
            return float(v.get("month_norm_hours", work_hours_norm))
    return work_hours_norm
