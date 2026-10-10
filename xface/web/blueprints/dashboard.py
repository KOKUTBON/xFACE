"""HTML Dashboard and Monitor view routes."""

from flask import Blueprint, render_template, redirect, url_for
from xface.web.blueprints.auth import login_required, monitor_access_required, is_logged_in
from xface.config import settings

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def index():
    """Root redirect to dashboard if logged in, otherwise monitor."""
    if is_logged_in():
        return redirect(url_for("dashboard.admin_dashboard"))
    return redirect(url_for("dashboard.live_monitor"))


@dashboard_bp.route("/dashboard")
@login_required
def admin_dashboard():
    """Main administrative dashboard for subject and image enrollment."""
    return render_template("dashboard.html", settings=settings)


@dashboard_bp.route("/monitor")
@monitor_access_required
def live_monitor():
    """Full-screen live entrance monitor for kiosk or door display."""
    return render_template("live_monitor.html", settings=settings)


@dashboard_bp.route("/logs")
@login_required
def access_logs():
    """Access logs and historical audit viewer."""
    return render_template("access_logs.html", settings=settings)
