"""Web app blueprint."""
from flask import Blueprint
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
