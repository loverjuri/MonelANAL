"""
Flask app: webhook endpoint for Telegram + cron endpoints for scheduled tasks + web app.
"""
import os
import subprocess
from pathlib import Path
from datetime import timedelta
from flask import Flask, request, jsonify, redirect, url_for

# Import process_update so it's available when webhook is hit
from bot.process_update import process_update
from config import SECRET_KEY, DEV_MODE

app = Flask(__name__)


def _internal_error_response(log_message: str):
    """Log details server-side without exposing implementation data to callers."""
    app.logger.error(log_message, exc_info=True)
    return jsonify({"ok": False, "error": "Internal server error"}), 500
app.config["SECRET_KEY"] = SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024
app.config["SESSION_COOKIE_SECURE"] = False if DEV_MODE else os.environ.get(
    "SESSION_COOKIE_SECURE", "1"
) == "1"
app.config["DEV_MODE"] = DEV_MODE
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["REMEMBER_COOKIE_DURATION"] = timedelta(minutes=15)
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=15)

# Rate limiting (optional - app works without flask-limiter if not installed)
try:
    from extensions import limiter
    limiter.init_app(app)
except ImportError:
    limiter = None

# Web app
from web import init_web
init_web(app)

# PythonAnywhere's default WSGI examples historically import ``application``.
# Keep this compatibility alias so an old WSGI file cannot produce an import
# error after the Flask object was named ``app``.
application = app


@app.before_request
def make_session_permanent():
    """Use server-side session lifetime for 15 min timeout."""
    from flask import session
    from flask_login import current_user
    if current_user.is_authenticated:
        session.permanent = True


@app.route("/", methods=["GET"])
def health():
    """Health check."""
    return "OK", 200


@app.route("/web", methods=["GET"])
def web_root():
    """Redirect /web to /web/."""
    return redirect(url_for("web.index"), code=302)


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


@app.route("/deploy", methods=["POST"])
def deploy():
    """Trigger a background GitHub-to-PythonAnywhere deployment."""
    expected = os.environ.get("DEPLOY_TOKEN", "").strip()
    provided = request.headers.get("X-Deploy-Token", "")
    if not expected or provided != expected:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    script = Path(__file__).resolve().parent / "deploy_paw.sh"
    if not script.exists():
        return jsonify({"ok": False, "error": "Deploy script is missing"}), 500
    try:
        subprocess.Popen(
            ["/bin/bash", str(script)],
            cwd=str(script.parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        app.logger.exception("deploy start failed: %s", exc)
        return jsonify({"ok": False, "error": "Could not start deploy"}), 500
    return jsonify({"ok": True, "message": "Deployment started"}), 202


def _check_cron_token():
    """Verify CRON_SECRET from a header (query fallback for old cron jobs)."""
    from config import CRON_SECRET
    if not CRON_SECRET:
        return app.debug
    token = request.headers.get("X-Cron-Token") or request.args.get("token")
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
        return _internal_error_response("cron task failed")


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
        return _internal_error_response("cron task failed")


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
        return _internal_error_response("cron task failed")


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
        return _internal_error_response("cron task failed")


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
        return _internal_error_response("cron task failed")


@app.route("/cron/subscriptions", methods=["GET"])
def cron_subscriptions():
    """Daily — Subscriptions due soon reminder."""
    if not _check_cron_token():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        from bot.prompts import send_subscriptions_reminder
        from config import get_chat_id
        chat_id = get_chat_id()
        if chat_id:
            send_subscriptions_reminder(int(chat_id))
        return "OK", 200
    except Exception as e:
        app.logger.exception("cron subscriptions: %s", e)
        return _internal_error_response("cron task failed")


@app.route("/cron/overspend-digest", methods=["GET"])
def cron_overspend_digest():
    """Daily — Overspend categories digest."""
    if not _check_cron_token():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        from bot.prompts import send_overspend_digest
        from config import get_chat_id
        chat_id = get_chat_id()
        if chat_id:
            send_overspend_digest(int(chat_id))
        return "OK", 200
    except Exception as e:
        app.logger.exception("cron overspend-digest: %s", e)
        return _internal_error_response("cron task failed")


@app.route("/cron/debt-reminders", methods=["GET"])
def cron_debt_reminders():
    """Daily — Debt payment reminders."""
    if not _check_cron_token():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        from bot.prompts import send_debt_reminders
        from config import get_chat_id
        chat_id = get_chat_id()
        if chat_id:
            send_debt_reminders(int(chat_id))
        return "OK", 200
    except Exception as e:
        app.logger.exception("cron debt-reminders: %s", e)
        return _internal_error_response("cron task failed")


@app.route("/cron/goal-deadline", methods=["GET"])
def cron_goal_deadline():
    """Monthly — Goal deadline reminders."""
    if not _check_cron_token():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        from bot.prompts import send_goal_deadline_reminder
        from config import get_chat_id
        chat_id = get_chat_id()
        if chat_id:
            send_goal_deadline_reminder(int(chat_id))
        return "OK", 200
    except Exception as e:
        app.logger.exception("cron goal-deadline: %s", e)
        return _internal_error_response("cron task failed")


@app.route("/cron/backup", methods=["GET"])
def cron_backup():
    """Daily — Auto backup."""
    if not _check_cron_token():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        from bot.prompts import send_auto_backup
        from config import get_chat_id
        chat_id = get_chat_id()
        if chat_id:
            send_auto_backup(int(chat_id))
        return "OK", 200
    except Exception as e:
        app.logger.exception("cron backup: %s", e)
        return _internal_error_response("cron task failed")


@app.route("/cron/auto-subscriptions", methods=["GET"])
def cron_auto_subscriptions():
    """Daily — Process auto-create subscriptions."""
    if not _check_cron_token():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        from bot.prompts import send_auto_subscriptions
        from config import get_chat_id
        chat_id = get_chat_id()
        if chat_id:
            send_auto_subscriptions(int(chat_id))
        return "OK", 200
    except Exception as e:
        app.logger.exception("cron auto-subscriptions: %s", e)
        return _internal_error_response("cron task failed")


@app.route("/cron/cleanup-logs", methods=["GET"])
def cron_cleanup_logs():
    """Weekly — Cleanup old logs."""
    if not _check_cron_token():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        from services.backup import cleanup_old_logs
        from db.repositories import get_session
        session = get_session()
        try:
            cleanup_old_logs(session, 30)
        finally:
            session.close()
        return "OK", 200
    except Exception as e:
        app.logger.exception("cron cleanup-logs: %s", e)
        return _internal_error_response("cron task failed")


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
        return _internal_error_response("cron task failed")


# WSGI entry point for PythonAnywhere
application = app


if __name__ == "__main__":
    app.run(host=os.environ.get("HOST", "127.0.0.1"),
            port=int(os.environ.get("PORT", "5000")),
            debug=DEV_MODE)
