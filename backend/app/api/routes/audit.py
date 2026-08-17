from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.user import User

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("")
def list_audit_logs(
    action: str | None = None,
    user_id: str | None = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[dict]:
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action == action)
    if user_id:
        import uuid

        query = query.filter(AuditLog.user_id == uuid.UUID(user_id))

    rows = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()
    return [
        {
            "id": str(row.id),
            "action": row.action,
            "user_email_snapshot": row.user_email_snapshot,
            "resource_type": row.resource_type,
            "resource_id": row.resource_id,
            "ip_address": row.ip_address,
            "extra": row.extra,
            "created_at": row.created_at.isoformat() if isinstance(row.created_at, datetime) else row.created_at,
        }
        for row in rows
    ]
