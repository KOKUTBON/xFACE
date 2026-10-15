"""Application configuration management with Pydantic for xFACE."""

import secrets
import os
from pathlib import Path
from typing import Optional, Union
from pydantic import Field, PrivateAttr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    """Strongly-typed application settings loaded from environment or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    _generated_secret_key: bool = PrivateAttr(default=False)
    _generated_dashboard_password: bool = PrivateAttr(default=False)

    # CompreFace Configuration
    HOST: str = Field(default="http://localhost", description="CompreFace host URL")
    PORT: int = Field(default=8000, description="CompreFace port")
    API_KEY: str = Field(default="", description="CompreFace Recognition Service API Key")
    DETECTION_PROBABILITY_THRESHOLD: float = Field(
        default=0.8,
        description="Minimum face detection confidence threshold"
    )
    SIMILARITY_THRESHOLD: float = Field(
        default=0.85,
        description="Minimum face similarity threshold for positive recognition"
    )
    FACE_PLUGINS: str = Field(
        default="",
        description="Comma-separated CompreFace plugins (e.g. 'age,gender')"
    )

    # Hardware & Access Control
    SHELLY_URL: Optional[str] = Field(
        default=None,
        description="URL for Shelly smart relay trigger"
    )
    SHELLY_TIMEOUT: float = Field(
        default=3.0,
        description="Timeout in seconds for Shelly HTTP requests"
    )
    SHELLY_COOLDOWN_SECONDS: float = Field(
        default=10.0,
        description="Cooldown period in seconds to avoid repeated triggers for the same person"
    )
    DEVICE_NAME: str = Field(
        default="Main Entrance",
        description="Human-readable name of the controlled door, stored in access logs"
    )

    # Security & Dashboard
    DASHBOARD_PASSWORD: str | None = Field(
        default=None,
        description="Admin password; if omitted, a random credential is created in DATA_DIR"
    )
    SECRET_KEY: str = Field(
        default="",
        description="Flask session secret key (a random one is generated when empty)"
    )
    MONITOR_REQUIRE_LOGIN: bool = Field(
        default=True,
        description="Require login for the live monitor, video stream and SSE events"
    )
    CORS_ORIGINS: str = Field(
        default="",
        description="Comma-separated list of origins allowed to call the API (empty disables CORS)"
    )

    # Public-safe operation is deliberately the default. Real biometrics and hardware
    # require an explicit opt-in in production configuration.
    DEMO_MODE: bool = Field(
        default=True,
        description="Use synthetic face/provider and door-controller implementations"
    )

    # Camera & Video Ingestion
    CAMERA_INDEX: Union[int, str] = Field(default=0, description="OpenCV camera device index or RTSP URL")
    CAMERA_WIDTH: int = Field(default=640, description="Camera capture width")
    CAMERA_HEIGHT: int = Field(default=480, description="Camera capture height")
    CAMERA_FPS: int = Field(default=30, description="Target camera frame rate")
    RECOGNITION_INTERVAL: float = Field(
        default=0.8,
        description="Interval in seconds between background recognition cycles"
    )

    # Database & Storage
    DATA_DIR: Path = Field(
        default=PROJECT_ROOT / "data",
        description="Directory for the SQLite database, snapshots and temporary files"
    )
    DATABASE_URL: str = Field(
        default="",
        description="SQLAlchemy database URL (defaults to SQLite inside DATA_DIR)"
    )
    SNAPSHOT_RETENTION_DAYS: int = Field(
        default=30,
        description="Delete access snapshots older than this many days (0 keeps them forever)"
    )

    # Web Server
    WEB_HOST: str = Field(default="0.0.0.0", description="Web interface bind host")
    WEB_PORT: int = Field(default=5000, description="Web interface bind port")
    DEBUG: bool = Field(default=False, description="Debug mode")

    @field_validator("HOST")
    @classmethod
    def clean_host_url(cls, v: str) -> str:
        return v.rstrip("/")

    @field_validator("CAMERA_INDEX", mode="before")
    @classmethod
    def parse_camera_index(cls, v):
        """Accept numeric device indexes as int and anything else (RTSP/HTTP URLs, device paths) as str."""
        if isinstance(v, str) and v.strip().isdigit():
            return int(v.strip())
        return v

    @model_validator(mode="after")
    def fill_derived_defaults(self) -> "Settings":
        self.DATA_DIR = Path(self.DATA_DIR).resolve()
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not self.DATABASE_URL:
            self.DATABASE_URL = f"sqlite:///{self.DATA_DIR / 'xface.db'}"
        if not self.SECRET_KEY:
            self.SECRET_KEY = secrets.token_hex(32)
            self._generated_secret_key = True
        if not self.DASHBOARD_PASSWORD:
            credential_file = self.DATA_DIR / ".admin_password"
            try:
                if credential_file.is_file():
                    self.DASHBOARD_PASSWORD = credential_file.read_text(encoding="utf-8").strip()
            except OSError:
                self.DASHBOARD_PASSWORD = None
            if not self.DASHBOARD_PASSWORD:
                self.DASHBOARD_PASSWORD = secrets.token_urlsafe(24)
                try:
                    fd = os.open(credential_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    with os.fdopen(fd, "w", encoding="utf-8") as handle:
                        handle.write(self.DASHBOARD_PASSWORD + "\n")
                except FileExistsError:
                    self.DASHBOARD_PASSWORD = credential_file.read_text(encoding="utf-8").strip()
                self._generated_dashboard_password = True
        return self

    @property
    def SNAPSHOTS_DIR(self) -> Path:
        return self.DATA_DIR / "snapshots"

    @property
    def uses_generated_dashboard_password(self) -> bool:
        return self._generated_dashboard_password

    @property
    def uses_generated_secret_key(self) -> bool:
        return self._generated_secret_key

    @property
    def cors_origins_list(self) -> list[str]:
        origins = [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]
        if "*" in origins:
            raise ValueError("CORS_ORIGINS must contain explicit trusted origins; '*' is not allowed")
        return origins

    @property
    def compreface_base_url(self) -> str:
        """Constructs the full base URL for CompreFace."""
        if f":{self.PORT}" in self.HOST:
            return self.HOST
        return f"{self.HOST}:{self.PORT}"


# Singleton instance
settings = Settings()
