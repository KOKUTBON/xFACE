"""Authentication Blueprint with secure session handling."""

from functools import wraps
from urllib.parse import urlsplit
from flask import Blueprint, request, render_template, redirect, url_for, session, flash, jsonify
from xface.config import settings
from xface.core.security import verify_password, hash_password

auth_bp = Blueprint("auth", __name__)

# Hash the configured password once at startup so it's never compared in plain text
_HASHED_ADMIN_PASSWORD = hash_password(settings.DASHBOARD_PASSWORD or "")


def is_logged_in() -> bool:
    return bool(session.get("logged_in"))


def _unauthorized():
    if request.is_json or request.path.startswith("/api/") or request.path.startswith("/video/"):
        return jsonify({"error": "Authentication required", "code": 401}), 401
    return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))


def login_required(f):
    """Decorator to require login for protected routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_logged_in():
            return _unauthorized()
        return f(*args, **kwargs)
    return decorated_function


def monitor_access_required(f):
    """Protect kiosk-facing routes (monitor, stream, SSE) only when MONITOR_REQUIRE_LOGIN is enabled."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if settings.MONITOR_REQUIRE_LOGIN and not is_logged_in():
            return _unauthorized()
        return f(*args, **kwargs)
    return decorated_function


def _safe_next_url(target: str | None) -> str:
    """Only allow redirects to local paths to prevent open-redirect attacks."""
    default = url_for("dashboard.admin_dashboard")
    if not target:
        return default
    parts = urlsplit(target)
    if parts.scheme or parts.netloc or not target.startswith("/") or target.startswith("//"):
        return default
    return target


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Admin login endpoint."""
    if is_logged_in():
        return redirect(url_for("dashboard.admin_dashboard"))

    if request.method == "POST":
        password = request.form.get("password", "")
        if verify_password(password, _HASHED_ADMIN_PASSWORD):
            session.clear()
            session["logged_in"] = True
            session["user"] = "admin"
            return redirect(_safe_next_url(request.args.get("next")))
        flash("Wrong password. Please try again.", "danger")

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    """Logout endpoint."""
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))
