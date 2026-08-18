"""Web app blueprint and lightweight CSRF protection."""
import hmac
import secrets
from flask import Blueprint, abort, request, session
from flask_login import LoginManager

web_bp = Blueprint("web", __name__, url_prefix="/web", template_folder="templates", static_folder="static")

login_manager = LoginManager()


def init_web(app):
    """Register web blueprint and configure Flask-Login."""
    from . import auth, views  # noqa: F401

    app.register_blueprint(web_bp)
    login_manager.init_app(app)
    login_manager.login_view = "web.login"
    login_manager.session_protection = "strong"
    login_manager.refresh_view = "web.login"

    @app.before_request
    def dev_auto_login():
        """Auto-login a local test account only when DEV_MODE is explicitly enabled."""
        if not app.config.get("DEV_MODE"):
            return
        from flask_login import current_user, login_user
        if current_user.is_authenticated:
            return
        if request.path.startswith("/web/static") or request.path in ("/web/login", "/web/logout"):
            return
        from werkzeug.security import generate_password_hash
        from db.models import User, get_session
        db = get_session()
        try:
            user = db.query(User).filter(User.username == "dev").first()
            if not user:
                user = User(username="dev", password_hash=generate_password_hash("dev"),
                            totp_verified=True)
                db.add(user); db.commit(); db.refresh(user)
            login_user(user, remember=False)
        finally:
            db.close()

    @app.context_processor
    def inject_csrf_token():
        def csrf_token():
            token = session.get("csrf_token")
            if not token:
                token = secrets.token_urlsafe(32)
                session["csrf_token"] = token
            return token
        return {"csrf_token": csrf_token}

    @app.before_request
    def validate_csrf():
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            return
        if request.endpoint in {"webhook", "web.telegram_login"} or request.path.startswith("/cron/"):
            return
        expected = session.get("csrf_token")
        provided = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
        if not expected or not provided or not hmac.compare_digest(expected, provided):
            abort(400, description="Invalid CSRF token")

    from db.models import User, get_session
    from db.repositories import get_user_by_id

    @login_manager.user_loader
    def load_user(user_id):
        try:
            session = get_session()
            try:
                return get_user_by_id(session, int(user_id))
            finally:
                session.close()
        except (ValueError, TypeError):
            return None
