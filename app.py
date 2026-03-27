import os
import secrets
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from flask import Flask, render_template, session

from models import db


def create_app():
    # Load config.env from the project root (next to app.py).
    base_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(base_dir, "config.env")
    load_dotenv(env_path)

    app = Flask(__name__, instance_relative_config=False)

    # ------------------------------------------------------------------
    # Core config
    # ------------------------------------------------------------------
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

    instance_dir = os.path.join(base_dir, "instance")
    os.makedirs(instance_dir, exist_ok=True)
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"sqlite:///{os.path.join(instance_dir, 'justask.db')}"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # ------------------------------------------------------------------
    # Session config
    # ------------------------------------------------------------------
    session_lifetime = int(os.environ.get("SESSION_LIFETIME_MINUTES", 30))
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=session_lifetime)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    # Enable Secure flag only in production (when served over HTTPS).
    app.config["SESSION_COOKIE_SECURE"] = (
        os.environ.get("FLASK_ENV", "production") != "development"
    )

    # ------------------------------------------------------------------
    # Extensions
    # ------------------------------------------------------------------
    db.init_app(app)

    from flask_migrate import Migrate
    Migrate(app, db)

    from extensions import limiter
    limiter.init_app(app)

    # ------------------------------------------------------------------
    # Blueprints
    # ------------------------------------------------------------------
    from routes.customer import customer_bp
    from routes.intranet import intranet_bp
    from routes.admin import admin_bp

    app.register_blueprint(customer_bp)
    app.register_blueprint(intranet_bp)
    app.register_blueprint(admin_bp)

    # ------------------------------------------------------------------
    # Jinja2 globals
    # ------------------------------------------------------------------
    from utils import t, csrf_token

    app.jinja_env.globals["t"] = t
    app.jinja_env.globals["csrf_token"] = csrf_token

    # ------------------------------------------------------------------
    # Context processors
    # ------------------------------------------------------------------
    @app.context_processor
    def inject_branding():
        return {
            "branding": {
                "company_name": os.environ.get("BRANDING_COMPANY_NAME", "justask"),
                "logo": os.environ.get("BRANDING_LOGO", "/static/img/logo.png"),
                "primary_color": os.environ.get("BRANDING_PRIMARY_COLOR", "#354660"),
                "secondary_color": os.environ.get(
                    "BRANDING_SECONDARY_COLOR", "#f26d40"
                ),
            }
        }

    @app.context_processor
    def inject_lang():
        lang = session.get(
            "lang", os.environ.get("DEFAULT_LANGUAGE", "de")
        )
        return {"lang": lang}

    @app.context_processor
    def inject_now():
        return {"now": datetime.now(timezone.utc)}

    # ------------------------------------------------------------------
    # Security headers
    # ------------------------------------------------------------------
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none'"
        )
        return response

    # ------------------------------------------------------------------
    # Error handlers
    # ------------------------------------------------------------------
    @app.errorhandler(400)
    def bad_request(e):
        try:
            return render_template("errors/400.html"), 400
        except Exception:
            return "Bad Request", 400

    @app.errorhandler(403)
    def forbidden(e):
        try:
            return render_template("errors/403.html"), 403
        except Exception:
            return "Forbidden", 403

    @app.errorhandler(404)
    def not_found(e):
        try:
            return render_template("errors/404.html"), 404
        except Exception:
            return "Not Found", 404

    @app.errorhandler(500)
    def internal_error(e):
        # Log the real error server-side but never expose details to the user.
        app.logger.exception("Internal server error: %s", e)
        try:
            return render_template("errors/500.html"), 500
        except Exception:
            return "Internal Server Error", 500

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1")
