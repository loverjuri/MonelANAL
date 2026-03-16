"""In-memory cache for status/budget to reduce CPU on PythonAnywhere (TTL 90s)."""
import time

_STATUS_CACHE = {}
_BUDGET_CACHE = {}
_CACHE_TTL = 90  # seconds


def get_cached_status():
    """Return cached dashboard status or None if expired."""
    now = time.time()
    if "status" in _STATUS_CACHE:
        data, ts = _STATUS_CACHE["status"]
        if now - ts < _CACHE_TTL:
            return data
    return None


def set_cached_status(data: dict):
    _STATUS_CACHE["status"] = (data, time.time())


def get_cached_budget(month_year: str):
    """Return cached budget status or None if expired."""
    now = time.time()
    if month_year in _BUDGET_CACHE:
        data, ts = _BUDGET_CACHE[month_year]
        if now - ts < _CACHE_TTL:
            return data
    return None


def set_cached_budget(month_year: str, data: dict):
    _BUDGET_CACHE[month_year] = (data, time.time())


def invalidate_status():
    """Clear status cache (call after writes that affect dashboard)."""
    _STATUS_CACHE.clear()


def invalidate_budget(month_year: str = None):
    """Clear budget cache for month or all."""
    if month_year:
        _BUDGET_CACHE.pop(month_year, None)
    else:
        _BUDGET_CACHE.clear()
