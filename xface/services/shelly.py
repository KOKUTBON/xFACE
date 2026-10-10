"""Shelly smart relay controller with cooldown and resilience."""

import time
import threading
import logging
from typing import Optional, Dict
from urllib.parse import urlsplit
import requests
from xface.config import settings

logger = logging.getLogger(__name__)


class ShellyService:
    """Manages communication with Shelly IoT relays for door unlocking."""

    def __init__(
        self,
        url: Optional[str] = settings.SHELLY_URL,
        timeout: float = settings.SHELLY_TIMEOUT,
        cooldown_seconds: float = settings.SHELLY_COOLDOWN_SECONDS
    ):
        self.url = url
        self.timeout = timeout
        self.cooldown_seconds = cooldown_seconds

        self._lock = threading.Lock()
        self._last_trigger_time: float = 0.0
        self._subject_last_seen: Dict[str, float] = {}
        self._consecutive_errors: int = 0
        self._is_online: bool = True

    def can_trigger_for_subject(self, subject_name: str) -> bool:
        """Check whether enough time has passed since this subject last triggered access."""
        with self._lock:
            now = time.time()
            # Check global rapid-fire throttle (minimum 1.5 seconds between physical relay strikes)
            if now - self._last_trigger_time < 1.5:
                return False

            last_time = self._subject_last_seen.get(subject_name, 0.0)
            return (now - last_time) >= self.cooldown_seconds

    def trigger_relay(self, subject_name: Optional[str] = None, force: bool = False) -> bool:
        """
        Trigger the Shelly relay to open the door.
        Respects cooldown per subject unless force is True.
        """
        if not self.url:
            logger.info("SHELLY_URL not configured; relay trigger skipped.")
            return False

        if subject_name and not force and not self.can_trigger_for_subject(subject_name):
            logger.info(f"Relay trigger suppressed by cooldown for subject: {subject_name}")
            return False

        try:
            logger.info(f"Triggering Shelly relay (subject: {subject_name or 'manual'})...")
            response = requests.get(self.url, timeout=self.timeout)

            if response.ok:
                with self._lock:
                    now = time.time()
                    self._last_trigger_time = now
                    if subject_name:
                        self._subject_last_seen[subject_name] = now
                    self._consecutive_errors = 0
                    self._is_online = True
                logger.info(f"Shelly relay activated successfully (Status: {response.status_code})")
                return True
            else:
                logger.error(f"Shelly returned HTTP error {response.status_code}: {response.text}")
                with self._lock:
                    self._consecutive_errors += 1
                return False

        except requests.exceptions.Timeout:
            logger.error(f"Shelly request timed out after {self.timeout}s.")
            with self._lock:
                self._consecutive_errors += 1
                self._is_online = False
            return False
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Shelly connection error: {e}")
            with self._lock:
                self._consecutive_errors += 1
                self._is_online = False
            return False
        except Exception as e:
            logger.error(f"Unexpected error communicating with Shelly: {e}")
            with self._lock:
                self._consecutive_errors += 1
            return False

    @property
    def device_base_url(self) -> Optional[str]:
        """scheme://host[:port] of the configured relay, without path or query."""
        if not self.url:
            return None
        parts = urlsplit(self.url)
        if not parts.scheme or not parts.netloc:
            return None
        return f"{parts.scheme}://{parts.netloc}"

    def check_health(self) -> dict:
        """
        Ping the Shelly device and return its status.
        Uses the read-only /shelly info endpoint (available on Gen1 and Gen2+ devices),
        never the trigger URL, so a health check can't unlock the door.
        """
        if not self.url:
            return {"configured": False, "online": False, "status": "Not configured"}

        base_url = self.device_base_url
        if not base_url:
            return {"configured": True, "online": False, "error": "Invalid SHELLY_URL",
                    "last_trigger_time": self._last_trigger_time}

        try:
            res = requests.get(f"{base_url}/shelly", timeout=2.0)
            with self._lock:
                self._is_online = res.ok
            return {
                "configured": True,
                "online": res.ok,
                "status_code": res.status_code,
                "last_trigger_time": self._last_trigger_time
            }
        except Exception as e:
            with self._lock:
                self._is_online = False
            return {
                "configured": True,
                "online": False,
                "error": str(e),
                "last_trigger_time": self._last_trigger_time
            }


class MockDoorController(ShellyService):
    """No-op door controller used by the public demo; it never performs network I/O."""

    def __init__(self):
        super().__init__(url=None)

    def trigger_relay(self, subject_name: Optional[str] = None, force: bool = False) -> bool:
        logger.info("Mock door controller: simulated relay request for %s", subject_name or "manual")
        return True

    def check_health(self) -> dict:
        return {"configured": False, "online": True, "status": "Mock controller"}


# Public-safe by default: hardware requires DEMO_MODE=false.
shelly_service = MockDoorController() if settings.DEMO_MODE else ShellyService()
