"""REST API Blueprint for Subject and Face Enrollment management."""

import base64
import binascii
import logging
import cv2
import numpy as np
from flask import Blueprint, request, jsonify, Response
from xface.services.compreface import compreface_service
from xface.services.camera import camera_service
from xface.database.connection import get_db
from xface.database.models import SubjectMetadata
from xface.web.blueprints.auth import login_required
from xface.core.exceptions import CompreFaceException

logger = logging.getLogger(__name__)

api_subjects_bp = Blueprint("api_subjects", __name__, url_prefix="/api/v1")

MAX_SUBJECT_NAME_LENGTH = 128


class InvalidImageError(ValueError):
    """Raised when the request carries an unusable image payload."""


def _validate_subject_name(name: str) -> str | None:
    """Return an error message if the subject name is not acceptable, else None."""
    if not name:
        return "Subject name is required."
    if len(name) > MAX_SUBJECT_NAME_LENGTH:
        return f"Subject name must be at most {MAX_SUBJECT_NAME_LENGTH} characters."
    if any(ord(c) < 32 for c in name):
        return "Subject name contains invalid characters."
    return None


def _extract_image_bytes() -> bytes | None:
    """
    Read the image from the request: webcam capture ('capture_from_webcam=true'),
    multipart file ('image') or base64 / data-URL string ('photo_data').
    """
    if request.form.get("capture_from_webcam", "false").lower() == "true":
        image_bytes = camera_service.get_jpeg_frame()
        if not image_bytes:
            raise InvalidImageError("No webcam frame available. Is the camera running?")
        return _validate_image_bytes(image_bytes)

    upload = request.files.get("image")
    if upload and upload.filename:
        return _validate_image_bytes(upload.read())

    photo_data = request.form.get("photo_data")
    if photo_data:
        if "," in photo_data:
            photo_data = photo_data.split(",", 1)[1]
        try:
            return _validate_image_bytes(base64.b64decode(photo_data, validate=True))
        except binascii.Error as e:
            raise InvalidImageError("photo_data is not valid base64.") from e

    return None


def _validate_image_bytes(image_bytes: bytes) -> bytes:
    """Accept only decodable raster images, with bounded dimensions and payload size."""
    if not image_bytes or len(image_bytes) > 16 * 1024 * 1024:
        raise InvalidImageError("Image is empty or exceeds the 16 MB upload limit.")
    image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None or image.size == 0:
        raise InvalidImageError("Upload is not a valid image.")
    height, width = image.shape[:2]
    if width < 32 or height < 32 or width > 8000 or height > 8000:
        raise InvalidImageError("Image dimensions must be between 32 and 8000 pixels.")
    return image_bytes


@api_subjects_bp.route("/subjects", methods=["GET"])
@login_required
def list_subjects():
    """Retrieve all subjects and their face image IDs."""
    try:
        faces_map = compreface_service.list_faces()
        # Also ensure subjects without images appear
        for subj in compreface_service.list_subjects():
            faces_map.setdefault(subj, [])
        return jsonify(faces_map)
    except CompreFaceException as e:
        return jsonify({"error": f"CompreFace error: {e}"}), 502


@api_subjects_bp.route("/subjects", methods=["POST"])
@login_required
def create_subject():
    """
    Create a new subject with an initial photo.
    Supports file upload ('image'), base64 photo ('photo_data'), or direct webcam capture ('capture_from_webcam': true).
    """
    subject_name = request.form.get("subject", "").strip()
    error = _validate_subject_name(subject_name)
    if error:
        return jsonify({"error": error}), 400

    try:
        image_bytes = _extract_image_bytes()
    except InvalidImageError as e:
        return jsonify({"error": str(e)}), 400
    if not image_bytes:
        return jsonify({"error": "A valid image is required (file upload, base64 or webcam)."}), 400

    try:
        if subject_name in compreface_service.list_subjects():
            return jsonify({"error": f"Subject '{subject_name}' already exists."}), 409

        compreface_service.add_subject(subject_name)
        try:
            image_id = compreface_service.add_image_to_subject(subject_name, image_bytes)
        except CompreFaceException:
            # Don't leave an empty subject behind when the photo is rejected (e.g. no face found)
            try:
                compreface_service.delete_subject(subject_name)
            except CompreFaceException:
                logger.warning(f"Could not roll back subject '{subject_name}' after failed upload.")
            raise
    except CompreFaceException as e:
        return jsonify({"error": f"CompreFace error: {e}"}), 502

    with get_db() as db:
        if not db.query(SubjectMetadata).filter(SubjectMetadata.subject_name == subject_name).first():
            db.add(SubjectMetadata(subject_name=subject_name))

    return jsonify({
        "message": f"Subject '{subject_name}' created.",
        "subject": subject_name,
        "image_id": image_id
    }), 201


@api_subjects_bp.route("/subjects/<path:subject_name>/images", methods=["POST"])
@login_required
def add_image_to_subject(subject_name: str):
    """Add an additional training photo to an existing subject."""
    try:
        image_bytes = _extract_image_bytes()
    except InvalidImageError as e:
        return jsonify({"error": str(e)}), 400
    if not image_bytes:
        return jsonify({"error": "A valid image is required (file upload, base64 or webcam)."}), 400

    try:
        image_id = compreface_service.add_image_to_subject(subject_name, image_bytes)
    except CompreFaceException as e:
        return jsonify({"error": f"CompreFace error: {e}"}), 502

    return jsonify({
        "message": f"Photo added to '{subject_name}'.",
        "image_id": image_id
    }), 201


@api_subjects_bp.route("/subjects/<path:subject_name>", methods=["PUT"])
@login_required
def rename_subject(subject_name: str):
    """Rename an existing subject."""
    data = request.get_json(silent=True) or {}
    new_name = str(data.get("new_name", "")).strip()

    error = _validate_subject_name(new_name)
    if error:
        return jsonify({"error": error}), 400
    if new_name == subject_name:
        return jsonify({"message": "Name unchanged."})

    try:
        if new_name in compreface_service.list_subjects():
            return jsonify({"error": f"Subject '{new_name}' already exists."}), 409
        success = compreface_service.rename_subject(subject_name, new_name)
    except CompreFaceException as e:
        return jsonify({"error": f"CompreFace error: {e}"}), 502

    if not success:
        return jsonify({"error": "Rename was not applied."}), 400

    with get_db() as db:
        meta = db.query(SubjectMetadata).filter(SubjectMetadata.subject_name == subject_name).first()
        if meta:
            meta.subject_name = new_name
    return jsonify({"message": f"Subject renamed to '{new_name}'.", "subject": new_name})


@api_subjects_bp.route("/subjects/<path:subject_name>", methods=["DELETE"])
@login_required
def delete_subject(subject_name: str):
    """Delete a subject and all associated training images."""
    try:
        compreface_service.delete_subject(subject_name)
    except CompreFaceException as e:
        return jsonify({"error": f"CompreFace error: {e}"}), 502

    with get_db() as db:
        db.query(SubjectMetadata).filter(SubjectMetadata.subject_name == subject_name).delete()
    return jsonify({"message": f"Subject '{subject_name}' deleted."})


@api_subjects_bp.route("/images/<string:image_id>", methods=["DELETE"])
@login_required
def delete_image(image_id: str):
    """Delete a single face image."""
    try:
        compreface_service.delete_image(image_id)
    except CompreFaceException as e:
        return jsonify({"error": f"CompreFace error: {e}"}), 502
    return jsonify({"message": "Photo deleted."})


@api_subjects_bp.route("/proxy/images/<string:image_id>")
@login_required
def proxy_image(image_id: str):
    """Securely proxy CompreFace face images without leaking CompreFace API credentials."""
    result = compreface_service.proxy_image_bytes(image_id)
    if not result:
        return jsonify({"error": "Image not found"}), 404

    content, content_type = result
    return Response(content, mimetype=content_type, headers={"Cache-Control": "private, max-age=3600"})
