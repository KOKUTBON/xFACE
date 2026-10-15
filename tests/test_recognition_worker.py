"""Tests for autonomous RecognitionWorker in xFACE."""

from unittest.mock import patch
from xface.services.compreface import compreface_service
from xface.services.shelly import shelly_service
from xface.database.connection import get_db
from xface.database.models import AccessLog, SubjectMetadata
from xface.services.recognition_worker import RecognitionWorker


def _match(subject, similarity):
    return [{
        "box": {"probability": 0.98, "x_min": 50, "y_min": 50, "x_max": 200, "y_max": 200},
        "subjects": [{"subject": subject, "similarity": similarity}] if subject else []
    }]


def test_recognition_worker_toggle():
    """Verify start, pause, resume, and stop controls."""
    worker = RecognitionWorker(interval=0.5, similarity_threshold=0.85)
    assert not worker.is_active()

    worker.start()
    assert worker.is_active()

    worker.set_active(False)
    assert not worker.is_active()
    assert worker.get_latest_detection()["status"] == "PAUSED"

    worker.set_active(True)
    assert worker.is_active()

    worker.stop()
    assert not worker.is_active()


@patch.object(compreface_service, "recognize_frame")
@patch.object(shelly_service, "trigger_relay")
def test_recognition_worker_authorized_flow(mock_trigger, mock_recognize, sample_frame):
    """A positive match triggers the relay, is logged once, and updates the latest detection."""
    mock_recognize.return_value = _match("Alice Example", 0.93)
    mock_trigger.return_value = True

    worker = RecognitionWorker(interval=0.5, similarity_threshold=0.85, access_cooldown=60)
    worker._process_frame(sample_frame)

    detection = worker.get_latest_detection()
    assert detection["status"] == "AUTHORIZED"
    assert "Alice Example" in detection["message"]
    assert detection["faces"][0]["access_logged"] is True
    assert detection["faces"][0]["relay_triggered"] is True
    assert mock_trigger.call_count == 1

    # Same person seen again inside the cooldown: shown as authorized, but no new log or relay pulse
    worker._process_frame(sample_frame)
    detection = worker.get_latest_detection()
    assert detection["status"] == "AUTHORIZED"
    assert detection["faces"][0]["access_logged"] is False
    assert mock_trigger.call_count == 1

    with get_db() as db:
        logs = db.query(AccessLog).all()
        assert len(logs) == 1
        assert logs[0].status == "GRANTED"
        assert logs[0].relay_triggered is True
        meta = db.query(SubjectMetadata).filter_by(subject_name="Alice Example").one()
        assert meta.total_access_count == 1


@patch.object(compreface_service, "recognize_frame")
@patch.object(shelly_service, "trigger_relay")
def test_cooldown_applies_without_relay(mock_trigger, mock_recognize, sample_frame):
    """With no relay configured (trigger returns False) the log must still not be flooded."""
    mock_recognize.return_value = _match("Bob Example", 0.95)
    mock_trigger.return_value = False

    worker = RecognitionWorker(interval=0.5, similarity_threshold=0.85, access_cooldown=60)
    for _ in range(5):
        worker._process_frame(sample_frame)

    with get_db() as db:
        assert db.query(AccessLog).count() == 1


@patch.object(compreface_service, "recognize_frame")
def test_below_threshold_is_logged_as_denied(mock_recognize, sample_frame):
    """A candidate below the threshold is denied and the closest match is kept in the notes."""
    mock_recognize.return_value = _match("Alice Example", 0.60)

    worker = RecognitionWorker(interval=0.5, similarity_threshold=0.85)
    worker._process_frame(sample_frame)
    worker._process_frame(sample_frame)  # throttled, not logged again

    assert worker.get_latest_detection()["status"] == "DENIED"
    with get_db() as db:
        logs = db.query(AccessLog).all()
        assert len(logs) == 1
        assert logs[0].status == "DENIED"
        assert logs[0].subject_name is None
        assert "Alice Example" in logs[0].notes


@patch.object(compreface_service, "recognize_frame")
def test_face_without_candidates_is_unknown(mock_recognize, sample_frame):
    mock_recognize.return_value = _match(None, 0)

    worker = RecognitionWorker(interval=0.5, similarity_threshold=0.85)
    worker._process_frame(sample_frame)

    assert worker.get_latest_detection()["status"] == "UNKNOWN"
    with get_db() as db:
        assert db.query(AccessLog).one().status == "UNKNOWN"
