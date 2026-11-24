"""Recording who changed what.

``record_event`` adds an audit row to the current transaction, so the event
and the change it describes are committed (or rolled back) together.
"""

from sqlalchemy.orm import Session

from app.models.audit import AuditEvent
from app.models.user import User


def record_event(
    db: Session,
    *,
    company_id: int,
    actor: User,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    detail: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        company_id=company_id,
        actor_user_id=actor.id,
        actor_email=actor.email,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        detail=detail or {},
    )
    db.add(event)
    return event
