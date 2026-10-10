"""Video streaming and camera endpoints."""

from flask import Blueprint, Response, jsonify, send_file, abort
from xface.services.camera import camera_service
from xface.services.storage import storage_service
from xface.web.blueprints.auth import login_required, monitor_access_required

video_bp = Blueprint("video", __name__)


@video_bp.route("/stream")
@monitor_access_required
def stream():
    """
    High-performance multipart MJPEG video stream.
    Can be embedded directly into <img src="/video/stream">.
    """
    if not camera_service.is_running():
        try:
            camera_service.start()
        except Exception:
            pass

    return Response(
        camera_service.mjpeg_generator(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-cache, no-store"}
    )


@video_bp.route("/snapshot")
@monitor_access_required
def snapshot():
    """Return immediate single frame JPEG image."""
    jpeg = camera_service.get_jpeg_frame()
    if jpeg:
        return Response(jpeg, mimetype="image/jpeg", headers={"Cache-Control": "no-store"})
    return jsonify({"error": "No frame available"}), 503


@video_bp.route("/frame_base64")
@login_required
def frame_base64():
    """Return base64-encoded frame (used by the enrollment UI to preview a webcam capture)."""
    b64 = camera_service.get_base64_frame()
    if b64:
        return jsonify({"frame": b64})
    return jsonify({"error": "No frame available", "frame": None}), 503


@video_bp.route("/status")
@monitor_access_required
def status():
    """Camera health status and diagnostics."""
    return jsonify(camera_service.get_stats())


@video_bp.route("/snapshots/<filename>")
@login_required
def get_saved_snapshot(filename: str):
    """
    Safely serve stored access log snapshot.
    Protected against path traversal attacks.
    """
    path = storage_service.get_snapshot_path(filename)
    if not path or not path.is_file():
        abort(404)

    return send_file(path, mimetype="image/jpeg")
