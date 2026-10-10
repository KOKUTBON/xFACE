"""Tests for StorageService and path traversal defense."""

import tempfile
from pathlib import Path
import pytest
from xface.services.storage import StorageService
from xface.core.security import validate_path_within_directory
from xface.core.exceptions import SecurityException


def test_save_snapshot_and_retrieve(sample_frame):
    """Verify snapshot saving, validation and file persistence."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage = StorageService(base_dir=Path(tmp_dir))

        filename = storage.save_snapshot(sample_frame, prefix="test_access")
        assert filename is not None
        assert filename.startswith("test_access_")
        assert filename.endswith(".jpg")

        # Resolve path
        resolved = storage.get_snapshot_path(filename)
        assert resolved is not None
        assert resolved.is_file()


def test_path_traversal_protection():
    """Verify that path traversal attempts are strictly blocked."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage = StorageService(base_dir=Path(tmp_dir))

        # Attempt to access /etc/passwd or parent directory
        malicious_filename = "../../../etc/passwd"
        result = storage.get_snapshot_path(malicious_filename)
        assert result is None


def test_validate_path_within_directory_raises():
    """Verify SecurityException is raised when child escapes parent directory."""
    with tempfile.TemporaryDirectory() as parent:
        outside = Path(parent).parent / "forbidden.txt"
        with pytest.raises(SecurityException):
            validate_path_within_directory(outside, parent)
