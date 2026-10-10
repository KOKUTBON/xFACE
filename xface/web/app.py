"""Application factory for xFACE Flask web service."""

import logging
import atexit
from flask import Flask, jsonify, request
from xface import __version__
from xface.config import settings
from xface.database.connection import init_db
from xface.services.camera import camera_service
from xface.services.recognition_worker import recognition_worker
from xface.web.blueprints import (
    auth_bp,
    dashboard_bp,
    video_bp,
    api_subjects_bp,
    api_logs_bp,
    api_system_bp,
)

logger = logging.getLogger(__name__)


def _wants_json() -> bool:
    return request.path.startswith("/api/") or request.path.startswith("/video/") or request.is_json


def _warn_about_insecure_defaults() -> None:
    if settings.uses_generated_dashboard_password:
        logger.warning(
            "DASHBOARD_PASSWORD was not supplied; a per-install credential was generated. "
            "Read the mode-600 %s file and replace it with a managed secret before production use.",
            settings.DATA_DIR / ".admin_password",
        )
    if settings.uses_generated_secret_key:
        logger.warning("SECRET_KEY is not set; using a random key. Sessions will be invalidated on every restart.")
    if not settings.API_KEY:
        logger.warning("API_KEY is not set; face recognition is disabled until a CompreFace key is configured.")


def create_app(start_services: bool = True) -> Flask:
    """Create and configure the xFACE application instance."""
    logging.basicConfig(
        level=logging.DEBUG if settings.DEBUG else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static"
    )

    app.config["SECRET_KEY"] = settings.SECRET_KEY
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB max upload

    # Cross-origin access is opt-in: the bundled UI is served from the same origin
    if settings.cors_origins_list:
        from flask_cors import CORS
        CORS(app, resources={r"/api/*": {"origins": settings.cors_origins_list}}, supports_credentials=True)

    init_db()

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(video_bp, url_prefix="/video")
    app.register_blueprint(api_subjects_bp)
    app.register_blueprint(api_logs_bp)
    app.register_blueprint(api_system_bp)

    @app.context_processor
    def inject_globals():
        return {"app_version": __version__, "monitor_require_login": settings.MONITOR_REQUIRE_LOGIN}

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        return response

    @app.errorhandler(404)
    def not_found(e):
        if _wants_json():
            return jsonify({"error": "Resource not found", "code": 404}), 404
        return "404 - Page not found", 404

    @app.errorhandler(413)
    def too_large(e):
        return jsonify({"error": "Uploaded file is too large (max 16 MB)", "code": 413}), 413

    @app.errorhandler(500)
    def server_error(e):
        if _wants_json():
            return jsonify({"error": "Internal server error", "code": 500}), 500
        return "500 - Internal server error", 500

    if start_services:
        _warn_about_insecure_defaults()

        try:
            camera_service.start()
        except Exception as e:
            logger.warning(f"Could not automatically start camera: {e}")

        try:
            recognition_worker.start()
        except Exception as e:
            logger.warning(f"Could not automatically start recognition worker: {e}")

        def cleanup_on_exit():
            logger.info("Shutting down background services...")
            try:
                recognition_worker.stop()
            except Exception:
                pass
            try:
                camera_service.stop()
            except Exception:
                pass

        atexit.register(cleanup_on_exit)

    logger.info("xFACE application created successfully.")
    return app
