"""Tests for CameraService verifying concurrency and deadlock prevention."""

from unittest.mock import MagicMock, patch
import numpy as np
from xface.services.camera import CameraService


def test_camera_service_init():
    """Verify camera service initializes with correct parameters."""
    cam = CameraService(camera_index=0, width=640, height=480, fps=15)
    assert cam.width == 640
    assert cam.height == 480
    assert cam.fps == 15
    assert not cam.is_running()


@patch("cv2.VideoCapture")
def test_camera_restart_no_deadlock(mock_video_capture):
    """
    CRITICAL REGRESSION TEST:
    Verify that calling restart() does NOT deadlock due to recursive lock acquisition.
    In the legacy code, restart_stream() acquired a non-reentrant Lock and then called
    stop_stream() and start_stream() which acquired the same Lock, causing immediate deadlock.
    """
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    # Return synthetic frame
    mock_cap.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
    mock_video_capture.return_value = mock_cap

    cam = CameraService(camera_index=0, width=640, height=480, fps=10)

    try:
        # Start capture
        cam.start()
        assert cam._running is True

        # Call restart multiple times - MUST NOT DEADLOCK!
        cam.restart()
        cam.restart()

        stats = cam.get_stats()
        assert stats["device"] == 0
        assert stats["resolution"] == "640x480"
    finally:
        cam.stop()
        assert not cam.is_running()


def test_camera_stats():
    """Verify stats dictionary returns required keys."""
    cam = CameraService()
    stats = cam.get_stats()
    assert "running" in stats
    assert "device" in stats
    assert "resolution" in stats
    assert "target_fps" in stats
