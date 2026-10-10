"""System control, health diagnostics, and real-time SSE stream."""

import time
import json
from flask import Blueprint, jsonify, request, Response
from xface import __version__
from xface.config import settings
from xface.services.camera import camera_service
from xface.services.compreface import compreface_service
from xface.services.shelly import shelly_service
from xface.services.recognition_worker import recognition_worker
from xface.database.connection import get_db
from xface.database.models import AccessLog
from xface.web.blueprints.auth import login_required, monitor_access_required, is_logged_in

api_system_bp = Blueprint("api_system", __name__, url_prefix="/api/v1/system")

SSE_HEARTBEAT_SECONDS = 15.0


@api_system_bp.route("/status", methods=["GET"])
def system_status():
    """
    Return health check of all integrated components.
    Anonymous callers (health checks, kiosk displays) only get online/offline flags;
    configuration details are reserved for authenticated admins.
    """
    camera_status = camera_service.get_stats()
    compreface_ok = compreface_service.check_health()
    shelly_status = shelly_service.check_health()
    recognition_active = recognition_worker.is_active()

    if not is_logged_in():
        return jsonify({
            "version": __version__,
            "camera": {
                "running": camera_status["running"],
                "resolution": camera_status["resolution"],
                "target_fps": camera_status["target_fps"],
            },
            "compreface": {"online": compreface_ok},
            "shelly": {"configured": shelly_status["configured"], "online": shelly_status["online"]},
            "recognition": {"active": recognition_active, "cooldown_seconds": recognition_worker.access_cooldown},
            "authenticated": False,
        })

    return jsonify({
        "version": __version__,
        "camera": camera_status,
        "compreface": {
            "online": compreface_ok,
            "configured": bool(compreface_service.api_key),
            "url": compreface_service.base_url
        },
        "shelly": {**shelly_status, "cooldown_seconds": shelly_service.cooldown_seconds},
        "recognition": {
            "active": recognition_active,
            "interval": recognition_worker.interval,
            "similarity_threshold": recognition_worker.similarity_threshold,
            "cooldown_seconds": recognition_worker.access_cooldown,
        },
        "authenticated": True,
    })


@api_system_bp.route("/camera/restart", methods=["POST"])
@login_required
def restart_camera():
    """Safely restart the camera device without deadlock."""
    try:
        opened = camera_service.restart()
    except Exception as e:
        return jsonify({"error": f"Camera restart failed: {e}"}), 500
    if opened:
        return jsonify({"status": "success", "message": "Camera restarted."})
    return jsonify({"error": "Camera restarted but the device could not be opened. Retrying in the background."}), 503


@api_system_bp.route("/recognition/toggle", methods=["POST"])
@login_required
def toggle_recognition():
    """Enable or disable autonomous background recognition."""
    data = request.get_json(silent=True) or {}
    active = data.get("active")

    if active is None:
        active = not recognition_worker.is_active()

    recognition_worker.set_active(bool(active))
    return jsonify({
        "status": "success",
        "recognition_active": recognition_worker.is_active()
    })


@api_system_bp.route("/shelly/trigger", methods=["POST"])
@login_required
def manual_shelly_trigger():
    """Manually activate the door relay with audit logging."""
    if not shelly_service.url:
        return jsonify({"error": "No relay configured. Set SHELLY_URL to enable door control."}), 400

    success = shelly_service.trigger_relay(subject_name=None, force=True)

    with get_db() as db:
        db.add(AccessLog(
            subject_name="Admin",
            status="MANUAL_OPEN",
            relay_triggered=success,
            device_name=settings.DEVICE_NAME,
            notes="Manual unlock from dashboard" if success else "Manual unlock failed: relay unreachable"
        ))

    if success:
        return jsonify({"status": "success", "message": "Door relay triggered."})
    return jsonify({"error": "Could not reach the Shelly relay. Check the connection."}), 502


@api_system_bp.route("/latest_detection", methods=["GET"])
@monitor_access_required
def latest_detection():
    """Return the most recent detection result for live UI overlay."""
    return jsonify(recognition_worker.get_latest_detection())


@api_system_bp.route("/events")
@monitor_access_required
def events_stream():
    """
    Server-Sent Events (SSE) stream for real-time live events.
    Allows instant update of entrance totem display without polling.
    """
    def event_generator():
        last_sent = None
        last_write = time.monotonic()
        while True:
            detection = recognition_worker.get_latest_detection()
            current_status = (detection.get("timestamp"), detection.get("status"), detection.get("message"))

            if current_status != last_sent:
                last_sent = current_status
                last_write = time.monotonic()
                yield f"data: {json.dumps(detection)}\n\n"
            elif time.monotonic() - last_write >= SSE_HEARTBEAT_SECONDS:
                # Comment line keeps idle connections alive through proxies
                last_write = time.monotonic()
                yield ": heartbeat\n\n"

            time.sleep(0.5)

    return Response(
        event_generator(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )
