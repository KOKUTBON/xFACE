"""Autonomous background facial recognition worker thread."""

import time
import threading
import logging
from typing import Optional, Dict, Any
import datetime
from xface.config import settings
from xface.services.camera import camera_service
from xface.services.compreface import compreface_service
from xface.services.shelly import shelly_service
from xface.services.storage import storage_service
from xface.database.connection import get_db
from xface.database.models import AccessLog, SubjectMetadata

logger = logging.getLogger(__name__)

# Minimum seconds between two logged unrecognized-face events (prevents log flooding)
UNKNOWN_LOG_INTERVAL = 5.0
# How often old snapshots are purged according to SNAPSHOT_RETENTION_DAYS
PURGE_INTERVAL = 3600.0


class RecognitionWorker:
    """
    Autonomous background worker that performs real-time face recognition.
    Operates independently of open browser tabs.
    """

    def __init__(
        self,
        interval: float = settings.RECOGNITION_INTERVAL,
        similarity_threshold: float = settings.SIMILARITY_THRESHOLD,
        access_cooldown: float = settings.SHELLY_COOLDOWN_SECONDS,
        device_name: str = settings.DEVICE_NAME,
    ):
        self.interval = interval
        self.similarity_threshold = similarity_threshold
        self.access_cooldown = access_cooldown
        self.device_name = device_name

        self._running = False
        self._active = True
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Cache of latest detection results for live UI overlay
        self._latest_detection: Dict[str, Any] = {
            "timestamp": None,
            "faces": [],
            "status": "IDLE",
            "message": "Waiting for faces..."
        }
        self._subject_last_access: Dict[str, float] = {}
        self._unknown_last_logged: float = 0.0
        self._last_purge: float = 0.0

    def start(self) -> None:
        """Start the background recognition thread."""
        with self._lock:
            if self._running:
                return

            self._running = True
            self._thread = threading.Thread(
                target=self._run_loop,
                name="RecognitionWorkerThread",
                daemon=True
            )
            self._thread.start()
            logger.info("Autonomous RecognitionWorker started.")

    def stop(self) -> None:
        """Stop the background recognition loop."""
        with self._lock:
            self._running = False
            thread = self._thread
            self._thread = None
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        logger.info("RecognitionWorker stopped.")

    def set_active(self, active: bool) -> None:
        """Pause or resume recognition without stopping camera capture."""
        with self._lock:
            self._active = active
            if not active:
                self._latest_detection = {
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "faces": [],
                    "status": "PAUSED",
                    "message": "Recognition paused"
                }
            logger.info(f"Recognition active set to: {active}")

    def is_active(self) -> bool:
        """Check if recognition is active."""
        with self._lock:
            return self._running and self._active

    def get_latest_detection(self) -> Dict[str, Any]:
        """Return the latest face detection bounding boxes and recognition results."""
        with self._lock:
            return self._latest_detection.copy()

    def _run_loop(self) -> None:
        """Core recognition loop executing in background."""
        while self._running:
            start_time = time.monotonic()

            if self._active and camera_service.is_running():
                try:
                    frame = camera_service.get_raw_frame()
                    if frame is not None and frame.size > 0:
                        self._process_frame(frame)
                except Exception as e:
                    logger.error(f"Error in recognition loop: {e}", exc_info=True)

            self._maybe_purge_snapshots()

            elapsed = time.monotonic() - start_time
            sleep_time = max(0.05, self.interval - elapsed)
            time.sleep(sleep_time)

    def _maybe_purge_snapshots(self) -> None:
        """Periodically enforce the snapshot retention policy."""
        if settings.SNAPSHOT_RETENTION_DAYS <= 0:
            return
        now = time.monotonic()
        if self._last_purge and now - self._last_purge < PURGE_INTERVAL:
            return
        self._last_purge = now
        try:
            removed = storage_service.purge_old_snapshots(settings.SNAPSHOT_RETENTION_DAYS)
            if removed:
                logger.info(f"Purged {removed} snapshots older than {settings.SNAPSHOT_RETENTION_DAYS} days.")
        except Exception as e:
            logger.warning(f"Snapshot purge failed: {e}")

    def _process_frame(self, frame) -> None:
        """Send frame to CompreFace, evaluate matches and trigger actions."""
        results = compreface_service.recognize_frame(frame)

        now_dt = datetime.datetime.now(datetime.timezone.utc)

        detection_summary = {
            "timestamp": now_dt.isoformat(),
            "faces": [],
            "status": "NO_FACES",
            "message": "No face detected"
        }

        if not results:
            with self._lock:
                self._latest_detection = detection_summary
            return

        detection_summary["status"] = "UNKNOWN"
        detection_summary["message"] = "Face not recognized"
        detected_faces = []
        unknown_logged = False

        for res in results:
            box = res.get("box", {})
            subjects = res.get("subjects", [])

            face_info = {
                "box": box,
                "subject": None,
                "similarity": 0.0,
                "status": "UNKNOWN",
                "access_logged": False,
                "relay_triggered": False,
            }

            best_match = max(subjects, key=lambda s: s.get("similarity", 0)) if subjects else None
            similarity = best_match.get("similarity", 0.0) if best_match else 0.0

            if best_match and similarity >= self.similarity_threshold:
                subject_name = best_match.get("subject", "Unknown")
                face_info.update(subject=subject_name, similarity=similarity, status="AUTHORIZED")
                detection_summary["status"] = "AUTHORIZED"
                detection_summary["message"] = f"Welcome, {subject_name}!"

                logged, relay_ok = self._handle_authorized_subject(subject_name, similarity, frame, now_dt)
                face_info["access_logged"] = logged
                face_info["relay_triggered"] = relay_ok
            else:
                status = "DENIED" if best_match else "UNKNOWN"
                face_info.update(similarity=similarity, status=status)
                if detection_summary["status"] != "AUTHORIZED":
                    detection_summary["status"] = status
                    detection_summary["message"] = "Face not authorized" if best_match else "Face not recognized"
                # Only one unknown event per frame, even with several unrecognized faces
                if not unknown_logged:
                    unknown_logged = self._handle_unknown_face(
                        frame, now_dt, similarity=similarity, status=status,
                        closest_subject=best_match.get("subject") if best_match else None
                    )
                    face_info["access_logged"] = unknown_logged

            detected_faces.append(face_info)

        detection_summary["faces"] = detected_faces

        with self._lock:
            self._latest_detection = detection_summary

    def _in_access_cooldown(self, subject_name: str) -> bool:
        last = self._subject_last_access.get(subject_name, 0.0)
        return (time.monotonic() - last) < self.access_cooldown if last else False

    def _handle_authorized_subject(self, subject_name: str, similarity: float, frame, now_dt) -> tuple[bool, bool]:
        """
        Handle access authorization, hardware relay, and database logging.
        Returns (access_logged, relay_triggered). Repeated recognitions of the same
        person inside the cooldown window are neither logged nor re-trigger the relay.
        """
        if self._in_access_cooldown(subject_name):
            logger.debug(f"Access granted for {subject_name}, but still in cooldown period.")
            return False, False

        self._subject_last_access[subject_name] = time.monotonic()
        relay_success = shelly_service.trigger_relay(subject_name=subject_name, force=True)

        snapshot_filename = storage_service.save_snapshot(frame, prefix="granted")

        try:
            with get_db() as db:
                db.add(AccessLog(
                    timestamp=now_dt,
                    subject_name=subject_name,
                    similarity=similarity,
                    status="GRANTED",
                    relay_triggered=relay_success,
                    device_name=self.device_name,
                    snapshot_filename=snapshot_filename,
                    notes=None if relay_success or not shelly_service.url else "Relay trigger failed"
                ))

                meta = db.query(SubjectMetadata).filter(
                    SubjectMetadata.subject_name == subject_name
                ).first()

                if meta:
                    meta.last_access_at = now_dt
                    meta.total_access_count += 1
                else:
                    db.add(SubjectMetadata(
                        subject_name=subject_name,
                        created_at=now_dt,
                        last_access_at=now_dt,
                        total_access_count=1
                    ))

            logger.info(
                f"ACCESS GRANTED for {subject_name} (similarity={similarity:.2f}, relay={relay_success})"
            )
        except Exception as e:
            logger.error(f"Failed to record access log in database: {e}")

        return True, relay_success

    def _handle_unknown_face(
        self, frame, now_dt, similarity: float, status: str = "UNKNOWN", closest_subject: Optional[str] = None
    ) -> bool:
        """Record an unrecognized face attempt, throttled to prevent log flooding. Returns True if logged."""
        now = time.monotonic()
        if self._unknown_last_logged and now - self._unknown_last_logged < UNKNOWN_LOG_INTERVAL:
            return False

        self._unknown_last_logged = now
        snapshot_filename = storage_service.save_snapshot(frame, prefix=status.lower())
        if status == "DENIED" and closest_subject:
            notes = f"Similarity below threshold (closest match: {closest_subject})"
        else:
            notes = "No matching subject"
        try:
            with get_db() as db:
                db.add(AccessLog(
                    timestamp=now_dt,
                    subject_name=None,
                    similarity=similarity if similarity > 0 else None,
                    status=status,
                    relay_triggered=False,
                    device_name=self.device_name,
                    snapshot_filename=snapshot_filename,
                    notes=notes
                ))
            logger.info(f"{status} face detected (similarity={similarity:.2f})")
        except Exception as e:
            logger.error(f"Failed to record unknown access log: {e}")
        return True


# Singleton recognition worker instance
recognition_worker = RecognitionWorker()
