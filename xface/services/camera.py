"""Robust, thread-safe Camera Service with deadlock prevention and MJPEG streaming."""

import cv2
import threading
import time
import base64
import logging
from typing import Optional, Generator
import numpy as np
from xface.config import settings
from xface.core.exceptions import CameraException

logger = logging.getLogger(__name__)


class CameraService:
    """
    Thread-safe camera streamer and frame hub.
    Uses re-entrant lock (RLock) to prevent deadlocks on restarts.
    """

    def __init__(
        self,
        camera_index: int | str = settings.CAMERA_INDEX,
        width: int = settings.CAMERA_WIDTH,
        height: int = settings.CAMERA_HEIGHT,
        fps: int = settings.CAMERA_FPS
    ):
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.fps = fps

        self._cap: Optional[cv2.VideoCapture] = None
        self._running = False
        self._capture_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        # Serializes start/stop/restart sequences coming from different threads
        self._lifecycle_lock = threading.Lock()

        # Re-entrant lock: restart() calls stop()/start() while already holding it
        self._lock = threading.RLock()

        self._current_raw_frame: Optional[np.ndarray] = None
        self._current_jpeg_frame: Optional[bytes] = None
        self._current_base64_frame: Optional[str] = None
        self._last_frame_time: float = 0.0
        self._frame_count: int = 0
        self._consecutive_failures: int = 0

    def start(self) -> bool:
        """
        Start the background camera capture thread.
        Returns True if the device was opened. When it cannot be opened the capture
        thread keeps retrying in the background, so a camera connected later is picked up.
        """
        with self._lock:
            if self._running:
                logger.debug("Camera stream already running.")
                return self._cap is not None and self._cap.isOpened()

            opened = True
            try:
                self._open_capture()
            except CameraException as e:
                opened = False
                logger.warning(f"{e}. Will keep retrying in the background.")

            self._running = True
            self._stop_event = threading.Event()
            self._capture_thread = threading.Thread(
                target=self._capture_loop,
                args=(self._stop_event,),
                name="CameraCaptureThread",
                daemon=True
            )
            self._capture_thread.start()
            logger.info(f"CameraService started on device {self.camera_index}")
            return opened

    def stop(self) -> None:
        """Stop capture and release hardware resources safely."""
        with self._lock:
            self._running = False
            self._stop_event.set()
            thread = self._capture_thread
            self._capture_thread = None

        # Join without holding the lock: the capture thread needs it to finish its iteration
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=2.0)

        with self._lock:
            self._release_capture()
            self._current_raw_frame = None
            self._current_jpeg_frame = None
            self._current_base64_frame = None
            logger.info("CameraService stopped and hardware released.")

    def restart(self) -> bool:
        """
        Safely restart camera capture.
        Safe against deadlocks thanks to RLock.
        """
        with self._lifecycle_lock:
            logger.info("Restarting CameraService...")
            self.stop()
            time.sleep(0.5)
            return self.start()

    def _open_capture(self) -> None:
        """Open OpenCV VideoCapture with optimal buffer configuration."""
        self._release_capture()
        self._cap = cv2.VideoCapture(self.camera_index)

        if not self._cap.isOpened():
            raise CameraException(f"Failed to open video capture device: {self.camera_index}")

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self._cap.set(cv2.CAP_PROP_FPS, self.fps)
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimal buffering to guarantee zero-latency

    def _release_capture(self) -> None:
        """Release underlying OpenCV VideoCapture device."""
        if self._cap:
            try:
                self._cap.release()
            except Exception as e:
                logger.warning(f"Error releasing VideoCapture: {e}")
            finally:
                self._cap = None

    def _capture_loop(self, stop_event: threading.Event) -> None:
        """Dedicated thread continuously pulling frames at target FPS."""
        frame_interval = 1.0 / max(self.fps, 1)
        max_failures = 10

        while not stop_event.is_set():
            start_time = time.monotonic()
            reconnect_backoff = False

            with self._lock:
                if stop_event.is_set():
                    break
                if not self._cap or not self._cap.isOpened():
                    self._consecutive_failures += 1
                else:
                    try:
                        ret, frame = self._cap.read()
                        if ret and frame is not None:
                            self._consecutive_failures = 0
                            self._frame_count += 1
                            self._last_frame_time = time.time()

                            # Normalize resolution
                            if frame.shape[1] != self.width or frame.shape[0] != self.height:
                                frame = cv2.resize(frame, (self.width, self.height))

                            self._current_raw_frame = frame

                            # Pre-encode to JPEG once, shared by the stream and snapshot endpoints
                            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 80]
                            success, buffer = cv2.imencode('.jpg', frame, encode_param)
                            if success:
                                self._current_jpeg_frame = buffer.tobytes()
                                self._current_base64_frame = None  # Lazy-loaded on demand
                        else:
                            self._consecutive_failures += 1
                    except Exception as e:
                        logger.error(f"Camera read error: {e}")
                        self._consecutive_failures += 1

                # Auto-reconnect after too many consecutive failures
                if self._consecutive_failures >= max_failures:
                    logger.debug(
                        f"{self._consecutive_failures} consecutive frame read failures, attempting auto-reconnect"
                    )
                    try:
                        self._open_capture()
                        logger.info("Camera reconnected.")
                    except Exception as e:
                        logger.debug(f"Auto-reconnect failed: {e}")
                    self._consecutive_failures = 0
                    reconnect_backoff = True

            # Wait outside the lock so readers are never blocked by a failing device
            if reconnect_backoff and not (self._cap and self._cap.isOpened()):
                stop_event.wait(2.0)
                continue

            # Keep a stable frame rate
            elapsed = time.monotonic() - start_time
            sleep_time = max(0.001, frame_interval - elapsed)
            time.sleep(sleep_time)

    def is_running(self) -> bool:
        """Check if camera is actively capturing."""
        with self._lock:
            return (
                self._running
                and self._cap is not None
                and self._cap.isOpened()
                and (time.time() - self._last_frame_time) < 3.0
            )

    def get_raw_frame(self) -> Optional[np.ndarray]:
        """Return the latest raw frame as NumPy ndarray (BGR)."""
        with self._lock:
            if self._current_raw_frame is not None:
                return self._current_raw_frame.copy()
            return None

    def get_jpeg_frame(self) -> Optional[bytes]:
        """Return the latest frame as JPEG bytes."""
        with self._lock:
            return self._current_jpeg_frame

    def get_base64_frame(self) -> Optional[str]:
        """Return the latest frame encoded as Base64 string."""
        with self._lock:
            if self._current_base64_frame is None and self._current_jpeg_frame is not None:
                self._current_base64_frame = base64.b64encode(self._current_jpeg_frame).decode("utf-8")
            return self._current_base64_frame

    def mjpeg_generator(self) -> Generator[bytes, None, None]:
        """Yield multipart MJPEG stream frames."""
        while True:
            jpeg = self.get_jpeg_frame()
            if jpeg:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
                )
            time.sleep(1.0 / max(self.fps, 10))

    def get_stats(self) -> dict:
        """Return runtime camera diagnostics."""
        with self._lock:
            return {
                "running": self.is_running(),
                "device": self.camera_index,
                "resolution": f"{self.width}x{self.height}",
                "target_fps": self.fps,
                "total_frames": self._frame_count,
                "last_frame_age_seconds": (
                    round(time.time() - self._last_frame_time, 2) if self._last_frame_time else None
                ),
            }


class MockCameraService:
    """Synthetic camera used in demo mode so startup cannot access a real camera."""

    def __init__(self):
        self.width, self.height, self.fps = 640, 480, 15
        self._running = False
        self._frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        cv2.putText(self._frame, "xFACE DEMO", (190, 245), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3)
        ok, encoded = cv2.imencode(".jpg", self._frame)
        self._jpeg = encoded.tobytes() if ok else None

    def start(self) -> bool:
        self._running = True
        return True

    def stop(self) -> None:
        self._running = False

    def restart(self) -> bool:
        self._running = True
        return True

    def is_running(self) -> bool:
        return self._running

    def get_raw_frame(self) -> Optional[np.ndarray]:
        return self._frame.copy() if self._running else None

    def get_jpeg_frame(self) -> Optional[bytes]:
        return self._jpeg if self._running else None

    def get_base64_frame(self) -> Optional[str]:
        return base64.b64encode(self._jpeg).decode("ascii") if self._running and self._jpeg else None

    def mjpeg_generator(self) -> Generator[bytes, None, None]:
        while self._running:
            if self._jpeg:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + self._jpeg + b"\r\n"
            time.sleep(1.0 / self.fps)

    def get_stats(self) -> dict:
        return {
            "running": self._running,
            "device": "synthetic-demo",
            "resolution": f"{self.width}x{self.height}",
            "target_fps": self.fps,
            "total_frames": 0,
            "last_frame_age_seconds": 0 if self._running else None,
        }


# Public-safe by default: a real camera requires DEMO_MODE=false.
camera_service = MockCameraService() if settings.DEMO_MODE else CameraService()
