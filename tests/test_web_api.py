"""Tests for Flask Web routes, authentication, and REST APIs."""

import datetime
from unittest.mock import patch
from xface.database.connection import get_db
from xface.database.models import AccessLog
from xface.core.exceptions import CompreFaceException


def _add_log(**kwargs):
    defaults = dict(subject_name="Alice Example", similarity=0.92, status="GRANTED",
                    relay_triggered=True, device_name="Main Entrance")
    defaults.update(kwargs)
    with get_db() as db:
        db.add(AccessLog(**defaults))


def test_login_and_logout(client):
    """Test login flow with valid and invalid passwords."""
    res = client.post("/login", data={"password": "wrongpassword"})
    assert res.status_code == 200
    assert b"Wrong password" in res.data

    res_ok = client.post("/login", data={"password": "unit-test-password"}, follow_redirects=False)
    assert res_ok.status_code == 302
    assert res_ok.headers["Location"].endswith("/dashboard")

    res_logout = client.get("/logout", follow_redirects=True)
    assert res_logout.status_code == 200
    assert b"signed out" in res_logout.data


def test_login_rejects_open_redirect(client):
    res = client.post("/login?next=https://evil.example/phish", data={"password": "unit-test-password"})
    assert res.status_code == 302
    assert res.headers["Location"].endswith("/dashboard")

    client.get("/logout")
    res_local = client.post("/login?next=/logs", data={"password": "unit-test-password"})
    assert res_local.headers["Location"].endswith("/logs")


def test_root_redirects(client, auth_client):
    assert client.get("/").headers["Location"].endswith("/dashboard")  # auth_client shares the session
    with client.session_transaction() as sess:
        sess.clear()
    assert client.get("/").headers["Location"].endswith("/monitor")


def test_protected_pages_redirect_to_login(client):
    for path in ("/dashboard", "/monitor", "/logs"):
        res = client.get(path)
        assert res.status_code == 302
        assert "/login" in res.headers["Location"]


def test_all_pages_render(auth_client):
    for path in ("/dashboard", "/monitor", "/logs"):
        res = auth_client.get(path)
        assert res.status_code == 200, path
    assert b"xFACE" in res.data


def test_monitor_and_video_are_protected_by_default(client):
    for path in ("/monitor", "/video/stream", "/video/snapshot", "/api/v1/system/latest_detection"):
        response = client.get(path)
        assert response.status_code in (302, 401), path
        if path.startswith("/monitor"):
            assert "/login" in response.headers["Location"]


def test_unauthenticated_api_protection(client):
    """Verify that protected API endpoints return 401 when not logged in."""
    for method, path in (
        ("get", "/api/v1/subjects"),
        ("get", "/api/v1/logs"),
        ("get", "/api/v1/logs/export"),
        ("post", "/api/v1/system/shelly/trigger"),
        ("post", "/api/v1/system/camera/restart"),
        ("post", "/api/v1/system/recognition/toggle"),
        ("get", "/video/frame_base64"),
        ("get", "/video/snapshots/whatever.jpg"),
    ):
        res = getattr(client, method)(path)
        assert res.status_code == 401, path
        assert "error" in res.get_json()


def test_system_status_endpoint(client, auth_client):
    """Public health check hides configuration details; admins get the full picture."""
    with client.session_transaction() as sess:
        sess.clear()
    data = client.get("/api/v1/system/status").get_json()
    for key in ("camera", "compreface", "shelly", "recognition"):
        assert key in data
    assert "url" not in data["compreface"]
    assert data["authenticated"] is False

    with client.session_transaction() as sess:
        sess["logged_in"] = True
    data = client.get("/api/v1/system/status").get_json()
    assert data["authenticated"] is True
    assert "url" in data["compreface"]
    assert "similarity_threshold" in data["recognition"]


def test_manual_trigger_without_relay_configured(auth_client):
    res = auth_client.post("/api/v1/system/shelly/trigger")
    assert res.status_code == 400
    assert "SHELLY_URL" in res.get_json()["error"]


def test_recognition_toggle(auth_client):
    res = auth_client.post("/api/v1/system/recognition/toggle", json={"active": False})
    assert res.status_code == 200
    assert res.get_json()["recognition_active"] is False


def test_access_logs_pagination_and_export(auth_client):
    """Verify logging API, pagination, and CSV export."""
    _add_log()
    _add_log(subject_name=None, similarity=None, status="UNKNOWN", relay_triggered=False)

    res = auth_client.get("/api/v1/logs?per_page=10")
    assert res.status_code == 200
    data = res.get_json()
    assert data["total"] == 2
    assert data["logs"][0]["timestamp"].endswith("+00:00")

    res = auth_client.get("/api/v1/logs?status=GRANTED")
    assert [log["subject_name"] for log in res.get_json()["logs"]] == ["Alice Example"]

    # Garbage pagination params fall back to defaults instead of crashing
    assert auth_client.get("/api/v1/logs?page=abc&per_page=-5").status_code == 200

    res_csv = auth_client.get("/api/v1/logs/export")
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.content_type
    assert b"Alice Example" in res_csv.data

    res_csv = auth_client.get("/api/v1/logs/export?status=UNKNOWN")
    assert b"Alice Example" not in res_csv.data


def test_access_logs_end_date_includes_whole_day(auth_client):
    day = datetime.datetime(2026, 1, 31, 18, 30)
    _add_log(timestamp=day)

    res = auth_client.get("/api/v1/logs?start_date=2026-01-31&end_date=2026-01-31")
    assert res.get_json()["total"] == 1
    res = auth_client.get("/api/v1/logs?end_date=2026-01-30")
    assert res.get_json()["total"] == 0
    res = auth_client.get("/api/v1/logs?start_date=2026-01-31T00:00:00.000Z&end_date=2026-01-31T23:59:59.999Z")
    assert res.get_json()["total"] == 1


def test_logs_stats(auth_client):
    _add_log()
    _add_log(subject_name=None, status="DENIED", relay_triggered=False)
    data = auth_client.get("/api/v1/logs/stats").get_json()
    assert data["total_accesses"] == 2
    assert data["granted_today"] == 1
    assert data["unknown_today"] == 1
    assert data["top_subjects"][0]["subject"] == "Alice Example"


@patch("xface.web.blueprints.api_subjects.compreface_service")
def test_create_subject_validation_and_rollback(mock_cf, auth_client, sample_jpeg):
    mock_cf.list_subjects.return_value = ["Alice Example"]
    import base64
    encoded = base64.b64encode(sample_jpeg).decode("ascii")

    res = auth_client.post("/api/v1/subjects", data={"subject": ""})
    assert res.status_code == 400

    res = auth_client.post("/api/v1/subjects", data={"subject": "Bob", "photo_data": "not base64!"})
    assert res.status_code == 400

    res = auth_client.post("/api/v1/subjects", data={"subject": "Alice Example", "photo_data": encoded})
    assert res.status_code == 409

    # Photo rejected by CompreFace (e.g. no face) -> subject creation is rolled back
    mock_cf.add_image_to_subject.side_effect = CompreFaceException("No face is found")
    res = auth_client.post("/api/v1/subjects", data={"subject": "Bob", "photo_data": encoded})
    assert res.status_code == 502
    mock_cf.delete_subject.assert_called_once_with("Bob")

    mock_cf.add_image_to_subject.side_effect = None
    mock_cf.add_image_to_subject.return_value = "img-1"
    res = auth_client.post("/api/v1/subjects", data={"subject": "Bob", "photo_data": encoded})
    assert res.status_code == 201
    assert res.get_json()["image_id"] == "img-1"


@patch("xface.web.blueprints.api_subjects.compreface_service")
def test_upload_validation_rejects_non_image(mock_cf, auth_client):
    mock_cf.list_subjects.return_value = []
    response = auth_client.post(
        "/api/v1/subjects",
        data={"subject": "Synthetic", "photo_data": "aGVsbG8="},
    )
    assert response.status_code == 400
    assert "valid image" in response.get_json()["error"]


@patch("xface.web.blueprints.api_subjects.compreface_service")
def test_rename_subject(mock_cf, auth_client):
    mock_cf.list_subjects.return_value = ["Alice Example", "Bob Example"]
    mock_cf.rename_subject.return_value = True

    res = auth_client.put("/api/v1/subjects/Alice%20Example", json={"new_name": "Bob Example"})
    assert res.status_code == 409

    res = auth_client.put("/api/v1/subjects/Alice%20Example", json={"new_name": "Alice Renamed"})
    assert res.status_code == 200
    mock_cf.rename_subject.assert_called_once_with("Alice Example", "Alice Renamed")


def test_unknown_routes(client):
    assert client.get("/api/v1/does-not-exist").get_json()["code"] == 404
    assert client.get("/does-not-exist").status_code == 404
