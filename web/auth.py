"""Authentication: login, logout, 2FA, Telegram Web App auto-login."""
import hashlib
import hmac
import json
import logging
import time
import requests
from flask import render_template, redirect, url_for, request, flash, jsonify
import flask
try:
    from extensions import limiter
except ImportError:
    limiter = None
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
import pyotp

from . import web_bp
from db.models import get_session, User
from db.repositories import get_user_by_username, get_user_by_telegram_id, get_user_by_id, update_user
from config import RECAPTCHA_SECRET_KEY, SECRET_KEY, BOT_TOKEN

log = logging.getLogger(__name__)


def verify_telegram_login(auth_data: dict) -> bool:
    """Verify Telegram Login Widget hash. See https://core.telegram.org/widgets/login"""
    if not BOT_TOKEN or "hash" not in auth_data:
        return False
    received_hash = auth_data.pop("hash", None)
    if not received_hash:
        return False
    data_check_arr = [f"{k}={v}" for k, v in auth_data.items()]
    data_check_arr.sort()
    data_check_string = "\n".join(data_check_arr)
    secret_key = hashlib.sha256(BOT_TOKEN.encode()).digest()
    computed = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed, received_hash):
        return False
    auth_date = int(auth_data.get("auth_date", 0))
    if auth_date and (time.time() - auth_date) > 86400:
        return False
    return True


def verify_telegram_webapp_init_data(init_data: str) -> dict | None:
    """Verify Telegram Web App initData. See core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app"""
    if not BOT_TOKEN or not init_data:
        return None
    from urllib.parse import parse_qs
    params = parse_qs(init_data, keep_blank_values=True)
    auth_data = {k: (v[0] if v else "") for k, v in params.items()}
    received_hash = auth_data.pop("hash", None)
    if not received_hash:
        return None
    data_check_arr = [f"{k}={v}" for k, v in sorted(auth_data.items())]
    data_check_string = "\n".join(data_check_arr)
    secret_key = hmac.new("WebAppData".encode(), BOT_TOKEN.encode(), hashlib.sha256).digest()
    computed = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed, received_hash):
        return None
    auth_date = int(auth_data.get("auth_date", 0))
    if auth_date and (time.time() - auth_date) > 86400:
        return None
    return auth_data


def verify_recaptcha(token: str) -> bool:
    """Verify reCAPTCHA v3 token."""
    if not RECAPTCHA_SECRET_KEY:
        return True  # Skip in dev
    try:
        r = requests.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={
                "secret": RECAPTCHA_SECRET_KEY,
                "response": token,
            },
            timeout=5,
        )
        data = r.json()
        return data.get("success") and data.get("score", 0) >= 0.5
    except Exception:
        return False


@web_bp.route("/login", methods=["GET", "POST"])
@(limiter.limit("3 per 15 minutes") if limiter else lambda f: f)
def login():
    if current_user.is_authenticated:
        return redirect(url_for("web.dashboard"))
    if request.method == "GET":
        from config import RECAPTCHA_SITE_KEY, BOT_USERNAME
        telegram_callback = url_for("web.telegram_login", _external=True) if BOT_USERNAME and BOT_TOKEN else None
        return render_template(
            "auth/login.html",
            recaptcha_site_key=RECAPTCHA_SITE_KEY,
            bot_username=BOT_USERNAME,
            telegram_callback=telegram_callback,
        )
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    recaptcha_token = request.form.get("g-recaptcha-response") or ""
    if not username or not password:
        from config import RECAPTCHA_SITE_KEY, BOT_USERNAME
        telegram_callback = url_for("web.telegram_login", _external=True) if BOT_USERNAME and BOT_TOKEN else None
        flash("Введите логин и пароль", "error")
        return render_template("auth/login.html", recaptcha_site_key=RECAPTCHA_SITE_KEY, bot_username=BOT_USERNAME, telegram_callback=telegram_callback)
    if RECAPTCHA_SECRET_KEY and not verify_recaptcha(recaptcha_token):
        from config import RECAPTCHA_SITE_KEY, BOT_USERNAME
        telegram_callback = url_for("web.telegram_login", _external=True) if BOT_USERNAME and BOT_TOKEN else None
        flash("Ошибка проверки капчи. Попробуйте снова.", "error")
        return render_template("auth/login.html", recaptcha_site_key=RECAPTCHA_SITE_KEY, bot_username=BOT_USERNAME, telegram_callback=telegram_callback)
    db_session = get_session()
    try:
        user = get_user_by_username(db_session, username)
        if not user or not check_password_hash(user.password_hash, password):
            from config import RECAPTCHA_SITE_KEY, BOT_USERNAME
            telegram_callback = url_for("web.telegram_login", _external=True) if BOT_USERNAME and BOT_TOKEN else None
            flash("Неверный логин или пароль", "error")
            return render_template("auth/login.html", recaptcha_site_key=RECAPTCHA_SITE_KEY, bot_username=BOT_USERNAME, telegram_callback=telegram_callback)
        if not user.totp_secret:
            from config import RECAPTCHA_SITE_KEY, BOT_USERNAME
            telegram_callback = url_for("web.telegram_login", _external=True) if BOT_USERNAME and BOT_TOKEN else None
            flash("2FA не настроен. Запустите create_web_user.py заново.", "error")
            return render_template("auth/login.html", recaptcha_site_key=RECAPTCHA_SITE_KEY, bot_username=BOT_USERNAME, telegram_callback=telegram_callback)
        flask.session["_user_id_for_2fa"] = user.id
        flask.session["_2fa_pending"] = True
        return redirect(url_for("web.twofa_verify"))
    finally:
        db_session.close()


@web_bp.route("/2fa/verify", methods=["GET", "POST"])
def twofa_verify():
    user_id = flask.session.get("_user_id_for_2fa")
    if not user_id:
        return redirect(url_for("web.login"))
    if request.method == "GET":
        return render_template("auth/2fa_verify.html")
    code = (request.form.get("code") or "").strip().replace(" ", "")
    if len(code) != 6 or not code.isdigit():
        flash("Введите 6-значный код", "error")
        return render_template("auth/2fa_verify.html")
    db_session = get_session()
    try:
        from db.repositories import get_user_by_id
        user = get_user_by_id(db_session, user_id)
        if not user or not user.totp_secret:
            flash("Ошибка сессии. Войдите снова.", "error")
            flask.session.pop("_user_id_for_2fa", None)
            flask.session.pop("_2fa_pending", None)
            return redirect(url_for("web.login"))
        totp = pyotp.TOTP(user.totp_secret)
        if not totp.verify(code, valid_window=1):
            flash("Неверный код", "error")
            return render_template("auth/2fa_verify.html")
        flask.session.pop("_user_id_for_2fa", None)
        flask.session.pop("_2fa_pending", None)
        login_user(user, remember=False)
        return redirect(url_for("web.dashboard"))
    finally:
        db_session.close()


def _do_telegram_login(telegram_id: str):
    """Find user by telegram_id and log in. Auto-links if single-user system."""
    db_session = get_session()
    try:
        user = get_user_by_telegram_id(db_session, str(telegram_id))
        if not user:
            # Single-user auto-link: if only one user exists and has no telegram link, bind now
            all_users = db_session.query(User).all()
            if len(all_users) == 1 and not all_users[0].telegram_user_id:
                all_users[0].telegram_user_id = str(telegram_id)
                db_session.commit()
                user = all_users[0]
                log.info("Auto-linked user %s to telegram_id=%s", user.username, telegram_id)
            else:
                log.warning("Telegram login failed: no user for telegram_id=%s", telegram_id)
                return None
        login_user(user, remember=True)
        log.info("Telegram login OK: user=%s telegram_id=%s", user.username, telegram_id)
        return True
    finally:
        db_session.close()


@web_bp.route("/telegram-login", methods=["GET", "POST"])
def telegram_login():
    """Callback for Telegram Login Widget (GET) or Web App auto-login (POST with initData)."""
    if current_user.is_authenticated:
        if request.method == "POST":
            return jsonify({"ok": True, "redirect": url_for("web.dashboard", _external=False)})
        return redirect(url_for("web.dashboard"))
    if request.method == "POST":
        content_type = request.content_type or ""
        if "json" in content_type:
            init_data = (request.get_json(silent=True) or {}).get("initData", "")
        else:
            init_data = request.form.get("initData", "")
        if not init_data:
            log.warning("telegram-login POST: no initData (ct=%s)", content_type)
            return jsonify({"ok": False, "error": "No initData"}), 400
        auth_data = verify_telegram_webapp_init_data(init_data)
        if not auth_data:
            log.warning("telegram-login POST: initData validation failed (bot_token=%s)", bool(BOT_TOKEN))
            return jsonify({"ok": False, "error": "Invalid initData"}), 403
        telegram_id = auth_data.get("id")
        if not telegram_id and auth_data.get("user"):
            try:
                u = json.loads(auth_data["user"]) if isinstance(auth_data["user"], str) else auth_data["user"]
                telegram_id = u.get("id") if isinstance(u, dict) else None
            except (json.JSONDecodeError, TypeError):
                pass
        if not telegram_id:
            log.warning("telegram-login POST: no user id in auth_data keys=%s", list(auth_data.keys()))
            return jsonify({"ok": False, "error": "No user id"}), 400
        if _do_telegram_login(str(telegram_id)):
            return jsonify({"ok": True, "redirect": url_for("web.dashboard", _external=False)})
        return jsonify({"ok": False, "error": "Account not linked"}), 403
    # GET — Telegram Login Widget callback
    auth_data = dict(request.args)
    if not verify_telegram_login(auth_data):
        flash("Ошибка авторизации через Telegram. Попробуйте снова.", "error")
        return redirect(url_for("web.login"))
    telegram_id = auth_data.get("id")
    if not telegram_id:
        flash("Некорректные данные от Telegram.", "error")
        return redirect(url_for("web.login"))
    if _do_telegram_login(str(telegram_id)):
        return redirect(url_for("web.dashboard"))
    flash("Этот аккаунт Telegram не привязан. Войдите по паролю и привяжите в настройках.", "error")
    return redirect(url_for("web.login"))


@web_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("web.login"))
