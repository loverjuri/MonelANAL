"""Authentication: login, logout, 2FA."""
import requests
from flask import render_template, redirect, url_for, request, flash, session
try:
    from extensions import limiter
except ImportError:
    limiter = None
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
import pyotp

from . import web_bp
from db.models import get_session
from db.repositories import get_user_by_username
from config import RECAPTCHA_SECRET_KEY, SECRET_KEY


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
        from config import RECAPTCHA_SITE_KEY
        return render_template("auth/login.html", recaptcha_site_key=RECAPTCHA_SITE_KEY)
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    recaptcha_token = request.form.get("g-recaptcha-response") or ""
    if not username or not password:
        from config import RECAPTCHA_SITE_KEY
        flash("Введите логин и пароль", "error")
        return render_template("auth/login.html", recaptcha_site_key=RECAPTCHA_SITE_KEY)
    if RECAPTCHA_SECRET_KEY and not verify_recaptcha(recaptcha_token):
        from config import RECAPTCHA_SITE_KEY
        flash("Ошибка проверки капчи. Попробуйте снова.", "error")
        return render_template("auth/login.html", recaptcha_site_key=RECAPTCHA_SITE_KEY)
    db_session = get_session()
    try:
        user = get_user_by_username(db_session, username)
        if not user or not check_password_hash(user.password_hash, password):
            from config import RECAPTCHA_SITE_KEY
            flash("Неверный логин или пароль", "error")
            return render_template("auth/login.html", recaptcha_site_key=RECAPTCHA_SITE_KEY)
        if not user.totp_secret:
            from config import RECAPTCHA_SITE_KEY
            flash("2FA не настроен. Запустите create_web_user.py заново.", "error")
            return render_template("auth/login.html", recaptcha_site_key=RECAPTCHA_SITE_KEY)
        session["_user_id_for_2fa"] = user.id
        session["_2fa_pending"] = True
        return redirect(url_for("web.twofa_verify"))
    finally:
        db_session.close()


@web_bp.route("/2fa/verify", methods=["GET", "POST"])
def twofa_verify():
    user_id = session.get("_user_id_for_2fa")
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
            session.pop("_user_id_for_2fa", None)
            session.pop("_2fa_pending", None)
            return redirect(url_for("web.login"))
        totp = pyotp.TOTP(user.totp_secret)
        if not totp.verify(code, valid_window=1):
            flash("Неверный код", "error")
            return render_template("auth/2fa_verify.html")
        session.pop("_user_id_for_2fa", None)
        session.pop("_2fa_pending", None)
        login_user(user, remember=False)
        return redirect(url_for("web.dashboard"))
    finally:
        db_session.close()


@web_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("web.login"))
