"""Resilient, high-performance CompreFace REST client without legacy SDK dependencies."""

import io
import time
import logging
from urllib.parse import quote
from typing import Optional, Dict, Any, List
import requests
import cv2
import numpy as np
from xface.config import settings
from xface.core.exceptions import CompreFaceException

logger = logging.getLogger(__name__)

# CompreFace error code returned (with HTTP 400) when the image contains no detectable face
NO_FACE_FOUND_CODE = 28


def _error_code(res: requests.Response) -> Optional[int]:
    try:
        return res.json().get("code")
    except ValueError:
        return None


class CompreFaceService:
    """
    Direct REST API client for CompreFace face recognition service.
    Avoids broken legacy SDK dependencies and incompatible requests-toolbelt versions.
    """

    def __init__(
        self,
        host: str = settings.HOST,
        port: int = settings.PORT,
        api_key: str = settings.API_KEY,
        det_prob_threshold: float = settings.DETECTION_PROBABILITY_THRESHOLD,
        similarity_threshold: float = settings.SIMILARITY_THRESHOLD,
        plugins: str = settings.FACE_PLUGINS
    ):
        self.host = host
        self.port = port
        self.api_key = api_key
        self.det_prob_threshold = det_prob_threshold
        self.similarity_threshold = similarity_threshold
        self.plugins = plugins

        self._session = requests.Session()
        # Pre-set headers for performance
        if self.api_key:
            self._session.headers.update({"x-api-key": self.api_key})

    @property
    def base_url(self) -> str:
        """Returns the full HTTP base URL for CompreFace."""
        if f":{self.port}" in self.host:
            return self.host
        return f"{self.host}:{self.port}"

    def retry(self, func, retries: int = 3, initial_delay: float = 0.5, backoff: float = 2.0):
        """Execute an API function with exponential backoff on network failures."""
        delay = initial_delay
        last_exc = None
        for attempt in range(1, retries + 1):
            try:
                return func()
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                last_exc = e
                logger.warning(f"CompreFace attempt {attempt}/{retries} failed: {e}. Retrying in {delay}s...")
                time.sleep(delay)
                delay *= backoff
            except CompreFaceException:
                raise
            except Exception as e:
                raise CompreFaceException(str(e)) from e
        raise CompreFaceException(f"All {retries} attempts failed: {last_exc}") from last_exc

    def check_health(self) -> bool:
        """Ping CompreFace subjects endpoint to verify reachability."""
        if not self.api_key:
            return False
        try:
            url = f"{self.base_url}/api/v1/recognition/subjects"
            res = self._session.get(url, timeout=3.0)
            return res.status_code == 200
        except Exception:
            return False

    def recognize_frame(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Recognize faces directly from an in-memory OpenCV frame (NumPy ndarray)
        without disk I/O.
        """
        if not self.api_key or frame is None or frame.size == 0:
            return []

        # Encode frame to JPEG buffer in memory
        success, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if not success:
            raise CompreFaceException("Failed to encode frame into JPEG buffer.")

        file_obj = io.BytesIO(buffer.tobytes())
        url = f"{self.base_url}/api/v1/recognition/recognize"
        params = {
            "limit": 0,
            "det_prob_threshold": self.det_prob_threshold,
            "prediction_count": 1,
        }
        if self.plugins:
            params["face_plugins"] = self.plugins

        def _do_request():
            file_obj.seek(0)
            res = self._session.post(
                url,
                params=params,
                files={"file": ("frame.jpg", file_obj, "image/jpeg")},
                timeout=6.0
            )
            if res.status_code == 400 and _error_code(res) == NO_FACE_FOUND_CODE:
                return []  # Normal idle state: nobody in front of the camera
            if not res.ok:
                raise CompreFaceException(f"CompreFace recognize error {res.status_code}: {res.text}")
            data = res.json()
            return data.get("result", [])

        try:
            return self.retry(_do_request, retries=2, initial_delay=0.3)
        except Exception as e:
            logger.error(f"Recognition request failed: {e}")
            return []

    def list_subjects(self) -> List[str]:
        """Fetch all registered subjects."""
        url = f"{self.base_url}/api/v1/recognition/subjects"
        def _fetch():
            res = self._session.get(url, timeout=5.0)
            if not res.ok:
                raise CompreFaceException(f"Failed to list subjects: {res.status_code} - {res.text}")
            return res.json().get("subjects", [])
        return self.retry(_fetch)

    def list_faces(self) -> Dict[str, List[str]]:
        """Fetch all face collections grouped by subject name."""
        url = f"{self.base_url}/api/v1/recognition/faces"
        def _fetch():
            res = self._session.get(url, timeout=6.0)
            if not res.ok:
                raise CompreFaceException(f"Failed to list faces: {res.status_code} - {res.text}")
            faces_map: Dict[str, List[str]] = {}
            for item in res.json().get("faces", []):
                subj = item.get("subject")
                img_id = item.get("image_id")
                if subj and img_id:
                    faces_map.setdefault(subj, []).append(img_id)
            return faces_map
        return self.retry(_fetch)

    def add_subject(self, subject_name: str) -> Dict[str, Any]:
        """Register a new subject."""
        url = f"{self.base_url}/api/v1/recognition/subjects"
        def _add():
            res = self._session.post(url, json={"subject": subject_name}, timeout=5.0)
            if not res.ok:
                raise CompreFaceException(f"Failed to add subject: {res.status_code} - {res.text}")
            return res.json()
        return self.retry(_add)

    def add_image_to_subject(self, subject_name: str, image_bytes_or_path: bytes | str) -> str:
        """Upload a training image for a subject."""
        url = f"{self.base_url}/api/v1/recognition/faces"
        params = {"subject": subject_name, "det_prob_threshold": self.det_prob_threshold}

        if isinstance(image_bytes_or_path, str):
            with open(image_bytes_or_path, "rb") as f:
                content = f.read()
        else:
            content = image_bytes_or_path

        def _upload():
            res = self._session.post(
                url,
                params=params,
                files={"file": ("face.jpg", io.BytesIO(content), "image/jpeg")},
                timeout=10.0
            )
            if res.status_code == 400 and _error_code(res) == NO_FACE_FOUND_CODE:
                raise CompreFaceException("No face was found in the image. Use a clear, front-facing photo.")
            if not res.ok:
                raise CompreFaceException(f"Failed to upload face image: {res.status_code} - {res.text}")
            data = res.json()
            image_id = data.get("image_id")
            if not image_id:
                raise CompreFaceException(f"No image_id returned by CompreFace: {data}")
            return image_id

        return self.retry(_upload)

    def rename_subject(self, old_name: str, new_name: str) -> bool:
        """Rename an existing subject."""
        url = f"{self.base_url}/api/v1/recognition/subjects/{quote(old_name, safe='')}"
        def _rename():
            res = self._session.put(url, json={"subject": new_name}, timeout=5.0)
            if not res.ok:
                raise CompreFaceException(f"Failed to rename subject: {res.status_code} - {res.text}")
            return bool(res.json().get("updated", True))
        return self.retry(_rename)

    def delete_subject(self, subject_name: str) -> bool:
        """Delete subject and all associated images."""
        url = f"{self.base_url}/api/v1/recognition/subjects/{quote(subject_name, safe='')}"
        def _delete():
            res = self._session.delete(url, timeout=10.0)
            if not res.ok and res.status_code != 404:
                raise CompreFaceException(f"Failed to delete subject: {res.status_code} - {res.text}")
            return True
        return self.retry(_delete)

    def delete_image(self, image_id: str) -> bool:
        """Delete a single face image by ID."""
        url = f"{self.base_url}/api/v1/recognition/faces/{quote(image_id, safe='')}"
        def _delete():
            res = self._session.delete(url, timeout=5.0)
            if not res.ok and res.status_code != 404:
                raise CompreFaceException(f"Failed to delete image: {res.status_code} - {res.text}")
            return True
        return self.retry(_delete)

    def proxy_image_bytes(self, image_id: str) -> Optional[tuple[bytes, str]]:
        """Fetch raw image binary and content-type."""
        url = f"{self.base_url}/api/v1/recognition/faces/{quote(image_id, safe='')}/img"
        try:
            res = self._session.get(url, timeout=8.0)
            if res.status_code == 200:
                content_type = res.headers.get("Content-Type", "image/jpeg")
                return res.content, content_type
        except Exception as e:
            logger.error(f"Error fetching CompreFace image {image_id}: {e}")
        return None


class MockFaceProvider:
    """Synthetic provider used by the public demo and tests; never calls CompreFace."""

    def __init__(self):
        self.api_key = ""
        self.base_url = "mock://synthetic"
        self._subjects: dict[str, list[str]] = {"Demo Subject": ["synthetic-demo-1"]}

    def check_health(self) -> bool:
        return True

    def recognize_frame(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        if frame is None or frame.size == 0:
            return []
        return [{
            "box": {"probability": 0.99, "x_min": 180, "y_min": 80, "x_max": 420, "y_max": 400},
            "subjects": [{"subject": "Demo Subject", "similarity": 0.97}],
        }]

    def list_subjects(self) -> List[str]:
        return list(self._subjects)

    def list_faces(self) -> Dict[str, List[str]]:
        return {name: list(images) for name, images in self._subjects.items()}

    def add_subject(self, subject_name: str) -> Dict[str, Any]:
        self._subjects.setdefault(subject_name, [])
        return {"subject": subject_name}

    def add_image_to_subject(self, subject_name: str, image_bytes_or_path: bytes | str) -> str:
        image_id = f"synthetic-{len(self._subjects.get(subject_name, [])) + 1}"
        self._subjects.setdefault(subject_name, []).append(image_id)
        return image_id

    def rename_subject(self, old_name: str, new_name: str) -> bool:
        if old_name not in self._subjects:
            return False
        self._subjects[new_name] = self._subjects.pop(old_name)
        return True

    def delete_subject(self, subject_name: str) -> bool:
        self._subjects.pop(subject_name, None)
        return True

    def delete_image(self, image_id: str) -> bool:
        for images in self._subjects.values():
            if image_id in images:
                images.remove(image_id)
        return True

    def proxy_image_bytes(self, image_id: str) -> Optional[tuple[bytes, str]]:
        return None


# Public-safe by default: selecting the real provider requires DEMO_MODE=false.
compreface_service = MockFaceProvider() if settings.DEMO_MODE else CompreFaceService()
