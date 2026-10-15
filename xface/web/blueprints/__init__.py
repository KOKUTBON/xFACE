"""Web Blueprints exports."""

from xface.web.blueprints.auth import auth_bp
from xface.web.blueprints.dashboard import dashboard_bp
from xface.web.blueprints.video import video_bp
from xface.web.blueprints.api_subjects import api_subjects_bp
from xface.web.blueprints.api_logs import api_logs_bp
from xface.web.blueprints.api_system import api_system_bp

__all__ = [
    "auth_bp",
    "dashboard_bp",
    "video_bp",
    "api_subjects_bp",
    "api_logs_bp",
    "api_system_bp",
]
