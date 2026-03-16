"""Production calendar: fetches from xmlcalendar.ru API, caches locally.
Fallback: weekday-based defaults (Mon–Fri 8h)."""
import json
import logging
from calendar import monthrange
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

from config import PROD_CALENDAR_PATH

TZ = ZoneInfo("Europe/Moscow")
log = logging.getLogger(__name__)

API_URL = "https://xmlcalendar.ru/data/ru/{year}/calendar.json"

# Structure: {"dates": {"2026-03-01": {"is_working": true, "work_hours": 8, "month_norm_hours": 176}, ...},
#             "fetched_years": [2026]}
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
            _CALENDAR = {"dates": {}, "fetched_years": []}
    else:
        _CALENDAR = {"dates": {}, "fetched_years": []}


def _save_calendar():
    PROD_CALENDAR_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PROD_CALENDAR_PATH, "w", encoding="utf-8") as f:
        json.dump(_CALENDAR, f, ensure_ascii=False, indent=2)


def _fetch_year_from_api(year: int) -> dict | None:
    """Fetch year data from xmlcalendar.ru. Returns parsed day dict or None."""
    import requests
    url = API_URL.format(year=year)
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            log.warning("prod_calendar API %s returned %s", url, resp.status_code)
            return None
        data = resp.json()
    except Exception as e:
        log.warning("prod_calendar API fetch failed: %s", e)
        return None

    # Build set of non-working days and shortened days per month
    non_working: dict[int, set[int]] = {}  # month -> set of non-working day numbers
    shortened: dict[int, set[int]] = {}    # month -> set of shortened day numbers

    for m_entry in data.get("months", []):
        m = int(m_entry["month"])
        non_working[m] = set()
        shortened[m] = set()
        for token in str(m_entry.get("days", "")).split(","):
            token = token.strip()
            if not token:
                continue
            if token.endswith("*"):
                # Shortened working day (pre-holiday, 7h) — it IS a working day
                day_num = int(token.rstrip("*"))
                shortened[m].add(day_num)
            elif token.endswith("+"):
                day_num = int(token.rstrip("+"))
                non_working[m].add(day_num)
            else:
                non_working[m].add(int(token))

    result = {}
    for m in range(1, 13):
        _, last_day = monthrange(year, m)
        month_hours = 0.0
        for d in range(1, last_day + 1):
            date_str = f"{year}-{m:02d}-{d:02d}"
            if d in non_working.get(m, set()):
                result[date_str] = {"is_working": False, "work_hours": 0}
            elif d in shortened.get(m, set()):
                result[date_str] = {"is_working": True, "work_hours": 7}
                month_hours += 7
            else:
                result[date_str] = {"is_working": True, "work_hours": 8}
                month_hours += 8
        # Set month_norm_hours on every day of this month
        for d in range(1, last_day + 1):
            date_str = f"{year}-{m:02d}-{d:02d}"
            result[date_str]["month_norm_hours"] = month_hours

    log.info("prod_calendar: fetched %d from API (%d days)", year, len(result))
    return result


def _generate_default_month(year: int, month: int) -> dict:
    """Fallback: weekday=working (8h), weekend=off."""
    _, last_day = monthrange(year, month)
    result = {}
    month_hours = 0.0
    for d in range(1, last_day + 1):
        dt = datetime(year, month, d)
        is_working = dt.weekday() < 5
        work_hours = 8 if is_working else 0
        month_hours += work_hours
        date_str = f"{year}-{month:02d}-{d:02d}"
        result[date_str] = {"is_working": is_working, "work_hours": work_hours}
    for d in range(1, last_day + 1):
        date_str = f"{year}-{month:02d}-{d:02d}"
        result[date_str]["month_norm_hours"] = month_hours
    return result


def _ensure_year(year: int):
    """Make sure calendar has data for the given year (API or default)."""
    _load_calendar()
    fetched = _CALENDAR.get("fetched_years", [])
    if year in fetched:
        return
    # Try API
    api_data = _fetch_year_from_api(year)
    if api_data:
        _CALENDAR.setdefault("dates", {}).update(api_data)
        if year not in fetched:
            fetched.append(year)
        _CALENDAR["fetched_years"] = fetched
        _save_calendar()
        return
    # Fallback: generate all 12 months
    for m in range(1, 13):
        prefix = f"{year}-{m:02d}-"
        if not any(k.startswith(prefix) for k in _CALENDAR.get("dates", {})):
            _CALENDAR.setdefault("dates", {}).update(_generate_default_month(year, m))
    _save_calendar()


def ensure_prod_calendar_updated():
    """Ensure current and next year exist in calendar."""
    now = datetime.now(TZ)
    _ensure_year(now.year)
    if now.month >= 11:
        _ensure_year(now.year + 1)


def refresh_calendar_from_api(year: int | None = None) -> bool:
    """Force re-fetch from API. Returns True if successful."""
    _load_calendar()
    if year is None:
        year = datetime.now(TZ).year
    api_data = _fetch_year_from_api(year)
    if not api_data:
        return False
    _CALENDAR.setdefault("dates", {}).update(api_data)
    fetched = _CALENDAR.get("fetched_years", [])
    if year not in fetched:
        fetched.append(year)
    _CALENDAR["fetched_years"] = fetched
    _save_calendar()
    return True


def get_month_norm_hours_for_date(date_str: str, session=None) -> float:
    """Return month norm hours for the month of date_str."""
    _load_calendar()
    default = 8.0 * 21
    try:
        parts = date_str[:10].split("-")
        if len(parts) < 2:
            return default
        year, month = int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return default

    prefix = f"{year}-{month:02d}-"
    for k, v in _CALENDAR.get("dates", {}).items():
        if k.startswith(prefix) and v.get("month_norm_hours"):
            return float(v["month_norm_hours"])

    _ensure_year(year)
    for k, v in _CALENDAR.get("dates", {}).items():
        if k.startswith(prefix) and v.get("month_norm_hours"):
            return float(v["month_norm_hours"])

    return default


def is_working_day(date_str: str) -> bool:
    """Check if a given date is a working day."""
    _load_calendar()
    try:
        parts = date_str[:10].split("-")
        year = int(parts[0])
    except (ValueError, IndexError):
        return datetime.strptime(date_str[:10], "%Y-%m-%d").weekday() < 5
    _ensure_year(year)
    entry = _CALENDAR.get("dates", {}).get(date_str[:10])
    if entry:
        return entry.get("is_working", True)
    return datetime.strptime(date_str[:10], "%Y-%m-%d").weekday() < 5


def get_work_hours_for_date(date_str: str) -> float:
    """Return scheduled work hours for a specific date (8, 7 for shortened, 0 for non-working)."""
    _load_calendar()
    try:
        parts = date_str[:10].split("-")
        year = int(parts[0])
    except (ValueError, IndexError):
        return 8.0
    _ensure_year(year)
    entry = _CALENDAR.get("dates", {}).get(date_str[:10])
    if entry:
        return float(entry.get("work_hours", 8))
    dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
    return 8.0 if dt.weekday() < 5 else 0.0
