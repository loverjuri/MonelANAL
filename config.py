"""Configuration from environment variables."""
import os
from pathlib import Path

# Load .env if present (for local dev)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Base paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "bot.db"
PROD_CALENDAR_PATH = DATA_DIR / "prod_calendar.json"

# Ensure data dir exists
DATA_DIR.mkdir(exist_ok=True)

# Telegram (env preferred; Config table used as fallback when handlers run)
BOT_TOKEN: str = os.environ.get("BOT_TOKEN", "").strip()
CHAT_ID: str = os.environ.get("CHAT_ID", "").strip()


def get_chat_id() -> str:
    """Chat ID from env or Config table."""
    if CHAT_ID:
        return CHAT_ID.strip()
    try:
        from db.repositories import get_session, get_config_param
        session = get_session()
        try:
            v = get_config_param(session, "ChatID")
            return (v or "").strip()
        finally:
            session.close()
    except Exception:
        return ""

# Cron protection
CRON_SECRET: str = os.environ.get("CRON_SECRET", "").strip()

# Web app (reCAPTCHA v3)
RECAPTCHA_SITE_KEY: str = os.environ.get("RECAPTCHA_SITE_KEY", "").strip()
RECAPTCHA_SECRET_KEY: str = os.environ.get("RECAPTCHA_SECRET_KEY", "").strip()

# Flask secret (required for sessions)
SECRET_KEY: str = os.environ.get("SECRET_KEY", "").strip() or "dev-secret-change-in-prod"

# Timezone
TIMEZONE = "Europe/Moscow"
