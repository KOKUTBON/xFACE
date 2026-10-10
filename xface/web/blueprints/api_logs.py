"""REST API Blueprint for Access Logs, Analytics, and CSV Export."""

import csv
import io
import datetime
from flask import Blueprint, request, jsonify, Response
from sqlalchemy import func
from xface.database.connection import get_db
from xface.database.models import AccessLog, SubjectMetadata, to_utc_iso
from xface.web.blueprints.auth import login_required

api_logs_bp = Blueprint("api_logs", __name__, url_prefix="/api/v1")

EXPORT_MAX_ROWS = 100_000


def _int_arg(name: str, default: int, minimum: int = 1, maximum: int | None = None) -> int:
    try:
        value = int(request.args.get(name, default))
    except (TypeError, ValueError):
        value = default
    value = max(minimum, value)
    return min(value, maximum) if maximum else value


def _parse_date(value: str | None):
    """Parse an ISO date or datetime into a naive UTC datetime (the storage format)."""
    if not value:
        return None
    try:
        # Python 3.10 fromisoformat() doesn't accept the "Z" suffix produced by JS toISOString()
        dt = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    return dt


def _filtered_query(db):
    """Apply the shared status/subject/date filters used by the list and export endpoints."""
    query = db.query(AccessLog)

    status = request.args.get("status")
    subject = request.args.get("subject")
    start = _parse_date(request.args.get("start_date"))
    end_raw = request.args.get("end_date") or ""
    end = _parse_date(end_raw)

    if status:
        statuses = [s.strip().upper() for s in status.split(",") if s.strip()]
        query = query.filter(AccessLog.status.in_(statuses))
    if subject:
        query = query.filter(AccessLog.subject_name.ilike(f"%{subject}%"))
    if start:
        query = query.filter(AccessLog.timestamp >= start)
    if end:
        if len(end_raw) == 10:
            # A bare date as upper bound covers that whole day
            query = query.filter(AccessLog.timestamp < end + datetime.timedelta(days=1))
        else:
            query = query.filter(AccessLog.timestamp <= end)
    return query


@api_logs_bp.route("/logs", methods=["GET"])
@login_required
def get_logs():
    """Retrieve paginated access logs with filtering."""
    page = _int_arg("page", 1)
    per_page = _int_arg("per_page", 50, maximum=200)

    with get_db() as db:
        query = _filtered_query(db)
        total_count = query.count()
        logs = (
            query.order_by(AccessLog.timestamp.desc(), AccessLog.id.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        return jsonify({
            "page": page,
            "per_page": per_page,
            "total": total_count,
            "total_pages": (total_count + per_page - 1) // per_page,
            "logs": [log.to_dict() for log in logs]
        })


@api_logs_bp.route("/logs/stats", methods=["GET"])
@login_required
def get_stats():
    """
    Summary metrics and analytics. Clients may pass ?today_start=<ISO datetime> (their local
    midnight) so "today" matches their timezone; otherwise UTC midnight is used.
    """
    with get_db() as db:
        today_start = _parse_date(request.args.get("today_start")) or datetime.datetime.now(
            datetime.timezone.utc
        ).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)

        def count(*filters):
            return db.query(func.count(AccessLog.id)).filter(*filters).scalar() or 0

        total_accesses = count()
        today_accesses = count(AccessLog.timestamp >= today_start)
        granted_today = count(AccessLog.timestamp >= today_start, AccessLog.status == "GRANTED")
        unknown_today = count(
            AccessLog.timestamp >= today_start,
            AccessLog.status.in_(["UNKNOWN", "DENIED"])
        )
        total_subjects = db.query(func.count(SubjectMetadata.id)).scalar() or 0

        top_subjects = (
            db.query(AccessLog.subject_name, func.count(AccessLog.id).label("count"))
            .filter(AccessLog.status == "GRANTED", AccessLog.subject_name.isnot(None))
            .group_by(AccessLog.subject_name)
            .order_by(func.count(AccessLog.id).desc())
            .limit(5)
            .all()
        )

        return jsonify({
            "total_accesses": total_accesses,
            "today_accesses": today_accesses,
            "granted_today": granted_today,
            "unknown_today": unknown_today,
            "total_subjects": total_subjects,
            "top_subjects": [{"subject": s[0], "count": s[1]} for s in top_subjects]
        })


@api_logs_bp.route("/logs/export", methods=["GET"])
@login_required
def export_csv():
    """Export access logs (honoring the same filters as /logs) as a downloadable CSV."""
    with get_db() as db:
        logs = (
            _filtered_query(db)
            .order_by(AccessLog.timestamp.desc(), AccessLog.id.desc())
            .limit(EXPORT_MAX_ROWS)
            .all()
        )

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "id", "timestamp_utc", "subject", "similarity", "status",
            "relay_triggered", "device", "snapshot", "notes"
        ])

        for item in logs:
            writer.writerow([
                item.id,
                to_utc_iso(item.timestamp) or "",
                item.subject_name or "",
                f"{item.similarity:.4f}" if item.similarity is not None else "",
                item.status,
                "true" if item.relay_triggered else "false",
                item.device_name,
                item.snapshot_filename or "",
                item.notes or ""
            ])

    filename = f"xface_access_logs_{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
