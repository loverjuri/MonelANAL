"""Notification wrapper: quiet hours, channel settings."""
from datetime import datetime
from zoneinfo import ZoneInfo
from db.repositories import get_config_param, get_session

TZ = ZoneInfo("Europe/Moscow")


def should_send_now(session=None) -> bool:
    """Check if current time is outside quiet hours."""
    close_session = False
    if session is None:
        session = get_session()
        close_session = True
    try:
        start = get_config_param(session, "QuietHoursStart")
        end = get_config_param(session, "QuietHoursEnd")
        if not start or not end:
            return True
        try:
            h_start = int(start)
            h_end = int(end)
        except (ValueError, TypeError):
            return True
        now_h = datetime.now(TZ).hour
        if h_start < h_end:
            return not (h_start <= now_h < h_end)
        else:
            return not (now_h >= h_start or now_h < h_end)
    finally:
        if close_session:
            session.close()


def is_channel_enabled(session, channel_type: str) -> bool:
    """Check if notification channel is enabled."""
    import json
    channels_str = get_config_param(session, "NotificationChannels")
    if not channels_str:
        return True  # all enabled by default
    try:
        channels = json.loads(channels_str)
        return channel_type in channels
    except (json.JSONDecodeError, TypeError):
        return True
