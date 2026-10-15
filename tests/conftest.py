"""Pytest configuration and common fixtures for xFACE."""

import os
import tempfile

# Isolate the test run from any local .env and from real data. This must happen before
# importing xface, because settings and the database engine are created at import time.
_TEST_DATA_DIR = tempfile.mkdtemp(prefix="xface-tests-")
os.environ.update({
    "DATA_DIR": _TEST_DATA_DIR,
    "DATABASE_URL": f"sqlite:///{_TEST_DATA_DIR}/test.db",
    "API_KEY": "",
    "SHELLY_URL": "",
    "DASHBOARD_PASSWORD": "unit-test-password",
    "SECRET_KEY": "test-secret-key",
    "MONITOR_REQUIRE_LOGIN": "true",
    "DEMO_MODE": "true",
    "CORS_ORIGINS": "",
})

import shutil  # noqa: E402
import numpy as np  # noqa: E402
import pytest  # noqa: E402
from xface.database.connection import Base, engine, get_db  # noqa: E402
from xface.database.models import AccessLog, SubjectMetadata  # noqa: E402
from xface.web.app import create_app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def test_db():
    """Create the schema in the temporary test database."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    shutil.rmtree(_TEST_DATA_DIR, ignore_errors=True)


@pytest.fixture(autouse=True)
def clean_tables():
    """Start every test with empty tables."""
    with get_db() as db:
        db.query(AccessLog).delete()
        db.query(SubjectMetadata).delete()
    yield


@pytest.fixture
def app():
    """Create Flask test app without auto-starting hardware capture."""
    app = create_app(start_services=False)
    app.config.update({"TESTING": True})
    return app


@pytest.fixture
def client(app):
    """Test client for API testing."""
    return app.test_client()


@pytest.fixture
def auth_client(client):
    """Client with authenticated admin session."""
    with client.session_transaction() as sess:
        sess["logged_in"] = True
        sess["user"] = "admin"
    return client


@pytest.fixture
def sample_frame():
    """Generate a synthetic 640x480 black test image."""
    return np.zeros((480, 640, 3), dtype=np.uint8)


@pytest.fixture
def sample_jpeg(sample_frame):
    import cv2
    ok, encoded = cv2.imencode(".jpg", sample_frame)
    assert ok
    return encoded.tobytes()
