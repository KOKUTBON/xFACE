"""Tests for settings parsing."""

from xface.config import Settings
import pytest


def test_camera_index_accepts_int_and_url(monkeypatch):
    monkeypatch.setenv("CAMERA_INDEX", "2")
    assert Settings().CAMERA_INDEX == 2

    monkeypatch.setenv("CAMERA_INDEX", "rtsp://camera.local:554/stream1")
    assert Settings().CAMERA_INDEX == "rtsp://camera.local:554/stream1"


def test_secret_key_is_generated_when_missing(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "")
    s = Settings()
    assert s.uses_generated_secret_key
    assert len(s.SECRET_KEY) == 64

    monkeypatch.setenv("SECRET_KEY", "explicit")
    assert not Settings().uses_generated_secret_key


def test_database_url_defaults_to_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", "")
    s = Settings()
    assert s.DATABASE_URL == f"sqlite:///{tmp_path.resolve() / 'xface.db'}"
    assert s.SNAPSHOTS_DIR == tmp_path.resolve() / "snapshots"


def test_cors_origins_list(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://a.example, https://b.example")
    assert Settings().cors_origins_list == ["https://a.example", "https://b.example"]


def test_cors_wildcard_is_rejected(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "*")
    with pytest.raises(ValueError, match="explicit trusted origins"):
        Settings().cors_origins_list


def test_secure_defaults(monkeypatch, tmp_path):
    monkeypatch.delenv("DASHBOARD_PASSWORD", raising=False)
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", "")
    s = Settings()
    assert s.MONITOR_REQUIRE_LOGIN is True
    assert s.DEMO_MODE is True
    credential_file = tmp_path / ".admin_password"
    assert credential_file.stat().st_mode & 0o777 == 0o600
    assert s.DASHBOARD_PASSWORD
