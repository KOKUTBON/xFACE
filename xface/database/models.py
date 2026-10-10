"""SQLAlchemy database models for Access Logs, Metadata, and Events."""

import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Boolean,
    Text,
    Index
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


def to_utc_iso(value):
    """Serialize a timestamp as ISO-8601 UTC. SQLite returns naive datetimes that are stored in UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=datetime.timezone.utc)
    return value.isoformat()


class AccessLog(Base):
    """Stores every biometric access attempt and door unlock event."""
    __tablename__ = "access_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=utc_now, nullable=False, index=True)
    subject_name = Column(String(128), nullable=True, index=True)
    similarity = Column(Float, nullable=True)
    status = Column(String(32), nullable=False, default="UNKNOWN", index=True)  # GRANTED, DENIED, UNKNOWN, MANUAL_OPEN
    relay_triggered = Column(Boolean, default=False, nullable=False)
    device_name = Column(String(128), default="Main Entrance", nullable=False)
    snapshot_filename = Column(String(256), nullable=True)
    notes = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_access_timestamp_desc", timestamp.desc()),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": to_utc_iso(self.timestamp),
            "subject_name": self.subject_name,
            "similarity": round(self.similarity, 3) if self.similarity is not None else None,
            "status": self.status,
            "relay_triggered": self.relay_triggered,
            "device_name": self.device_name,
            "snapshot_filename": self.snapshot_filename,
            "notes": self.notes,
        }


class SubjectMetadata(Base):
    """Local metadata and statistics for enrolled subjects."""
    __tablename__ = "subjects_metadata"

    id = Column(Integer, primary_key=True, autoincrement=True)
    subject_name = Column(String(128), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    last_access_at = Column(DateTime, nullable=True)
    total_access_count = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    notes = Column(Text, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "subject_name": self.subject_name,
            "created_at": to_utc_iso(self.created_at),
            "last_access_at": to_utc_iso(self.last_access_at),
            "total_access_count": self.total_access_count,
            "is_active": self.is_active,
            "notes": self.notes,
        }


class SystemEvent(Base):
    """System diagnostic events, hardware connectivity issues and errors."""
    __tablename__ = "system_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=utc_now, nullable=False, index=True)
    level = Column(String(16), nullable=False, default="INFO")  # INFO, WARNING, ERROR
    source = Column(String(64), nullable=False)  # CAMERA, COMPREFACE, SHELLY, RECOGNITION, AUTH
    message = Column(Text, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": to_utc_iso(self.timestamp),
            "level": self.level,
            "source": self.source,
            "message": self.message,
        }
