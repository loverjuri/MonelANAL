"""
Flask app: webhook endpoint for Telegram + cron endpoints for scheduled tasks.
"""
from flask import Flask, request, jsonify

# Import process_update so it's available when webhook is hit
from bot.process_update import process_update

app = Flask(__name__)


@app.route("/", methods=["GET"])
def health():
    """Health check."""
    return "OK", 200


@app.route("/webhook", methods=["POST"])
def webhook():
    """Telegram webhook endpoint."""
    if not request.data:
        return "OK", 200
    try:
        update = request.get_json(force=True, silent=True)
        if not update:
            return "OK", 200
        process_update(update)
    except Exception as e:
        app.logger.exception("webhook error: %s", e)
    return "OK", 200


def _check_cron_token():
    """Verify CRON_SECRET from query param or header."""
    from config import CRON_SECRET
    if not CRON_SECRET:
        return True  # No secret configured — allow (dev only)
    token = request.args.get("token") or request.headers.get("X-Cron-Token")
    return token == CRON_SECRET


@app.route("/cron/main-work", methods=["GET"])
def cron_main_work():
    """18:00 — How was your work day?"""
    if not _check_cron_token():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        from bot.prompts import send_main_work_prompt
        from config import get_chat_id
        chat_id = get_chat_id()
        if chat_id:
            send_main_work_prompt(int(chat_id))
        return "OK", 200
    except Exception as e:
        app.logger.exception("cron main-work: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/cron/second-job", methods=["GET"])
def cron_second_job():
    """00:05 — Second job income for yesterday?"""
    if not _check_cron_token():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        from bot.prompts import send_second_job_prompt
        from config import get_chat_id
        chat_id = get_chat_id()
        if chat_id:
            send_second_job_prompt(int(chat_id))
        return "OK", 200
    except Exception as e:
        app.logger.exception("cron second-job: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/cron/payday", methods=["GET"])
def cron_payday():
    """10:00 on 10th and 25th — Payday prompt."""
    if not _check_cron_token():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("Europe/Moscow")
        now = datetime.now(tz)
        if now.day != 10 and now.day != 25:
            return "OK", 200  # Not payday
        from bot.prompts import send_payday_prompt
        from config import get_chat_id
        chat_id = get_chat_id()
        if chat_id:
            send_payday_prompt(int(chat_id))
        return "OK", 200
    except Exception as e:
        app.logger.exception("cron payday: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/cron/reminder-main", methods=["GET"])
def cron_reminder_main():
    """19:00 — Reminder for main work log."""
    if not _check_cron_token():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        from bot.prompts import send_reminder_main_work
        from config import get_chat_id
        chat_id = get_chat_id()
        if chat_id:
            send_reminder_main_work(int(chat_id))
        return "OK", 200
    except Exception as e:
        app.logger.exception("cron reminder-main: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/cron/reminder-second", methods=["GET"])
def cron_reminder_second():
    """00:30 — Reminder for second job."""
    if not _check_cron_token():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        from bot.prompts import send_reminder_second_job
        from config import get_chat_id
        chat_id = get_chat_id()
        if chat_id:
            send_reminder_second_job(int(chat_id))
        return "OK", 200
    except Exception as e:
        app.logger.exception("cron reminder-second: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/cron/prod-calendar", methods=["GET"])
def cron_prod_calendar():
    """1st of month — Update prod calendar (manual mode: no-op or regenerate default)."""
    if not _check_cron_token():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        from services.prod_calendar import ensure_prod_calendar_updated
        ensure_prod_calendar_updated()
        return "OK", 200
    except Exception as e:
        app.logger.exception("cron prod-calendar: %s", e)
        return jsonify({"error": str(e)}), 500


# WSGI entry point for PythonAnywhere
application = app
