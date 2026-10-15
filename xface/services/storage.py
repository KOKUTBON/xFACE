"""Secure file and snapshot storage service."""

import time
import uuid
import datetime
import logging
from pathlib import Path
from typing import Optional
import cv2
import numpy as np
from xface.config import settings
from xface.core.security import validate_path_within_directory, sanitize_filename

logger = logging.getLogger(__name__)


class StorageService:
    """Manages secure persistence for face snapshots, temporary files, and exports."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = Path(base_dir or settings.DATA_DIR).resolve()
        self.snapshots_dir = self.base_dir / "snapshots"
        self.temp_dir = self.base_dir / "temp"

        # Ensure directories exist
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def save_snapshot(self, frame: np.ndarray, prefix: str = "access") -> Optional[str]:
        """Save a frame snapshot to the secure snapshot directory. Returns filename."""
        if frame is None or frame.size == 0:
            return None

        prefix = sanitize_filename(prefix).replace(" ", "_")
        date_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        filename = f"{prefix}_{date_str}_{unique_id}.jpg"
        target_path = self.snapshots_dir / filename

        try:
            if not cv2.imwrite(str(target_path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85]):
                logger.error(f"OpenCV could not write snapshot {filename}")
                return None
            logger.debug(f"Saved snapshot: {filename}")
            return filename
        except Exception as e:
            logger.error(f"Failed to save snapshot {filename}: {e}")
            return None

    def get_snapshot_path(self, filename: str) -> Optional[Path]:
        """Resolve and validate that the snapshot file exists and is strictly inside snapshots_dir."""
        safe_name = sanitize_filename(filename)
        candidate = self.snapshots_dir / safe_name
        try:
            validated = validate_path_within_directory(candidate, self.snapshots_dir)
            if validated.is_file():
                return validated
        except Exception as e:
            logger.warning(f"Path traversal or invalid file rejected: {e}")
        return None

    def save_temp_image(self, file_bytes: bytes, original_name: str = "upload.jpg") -> Path:
        """Save raw bytes to a validated temporary file."""
        safe_name = sanitize_filename(original_name)
        unique_name = f"temp_{uuid.uuid4().hex[:8]}_{safe_name}"
        target_path = self.temp_dir / unique_name
        validated = validate_path_within_directory(target_path, self.temp_dir)

        with open(validated, "wb") as f:
            f.write(file_bytes)

        return validated

    def cleanup_temp(self) -> int:
        """Remove all temporary files in temp_dir. Returns count removed."""
        count = 0
        for entry in self.temp_dir.iterdir():
            try:
                if entry.is_file():
                    entry.unlink()
                    count += 1
            except Exception as e:
                logger.error(f"Error removing temp file {entry}: {e}")
        return count

    def purge_old_snapshots(self, max_age_days: int = 30) -> int:
        """Delete snapshots older than max_age_days."""
        count = 0
        cutoff = time.time() - max_age_days * 86400
        for entry in self.snapshots_dir.glob("*.jpg"):
            try:
                if entry.stat().st_mtime < cutoff:
                    entry.unlink()
                    count += 1
            except Exception as e:
                logger.warning(f"Failed to delete old snapshot {entry}: {e}")
        return count


# Singleton storage instance
storage_service = StorageService()
