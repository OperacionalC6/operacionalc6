import uuid

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def log_action(
    db: Session,
    *,
    action: str,
    user_id: uuid.UUID | None = None,
    user_email_snapshot: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    extra: dict | None = None,
) -> None:
    """
    Registra uma entrada de auditoria. Commita de forma independente para que
    uma falha de auditoria nunca reverta a transação de negócio, e para que o
    log persista mesmo se a operação principal falhar.
    """
    entry = AuditLog(
        action=action,
        user_id=user_id,
        user_email_snapshot=user_email_snapshot,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        user_agent=user_agent,
        extra=extra,
    )
    db.add(entry)
    db.commit()
