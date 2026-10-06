from sqlalchemy.orm import Session
from .models import AuditLog
from typing import Optional

def log_action(
    db: Session,
    action: str,
    actor = None,
    target_id: Optional[int] = None,
    target_dni: Optional[str] = None,
    target_name: Optional[str] = None,
    details: Optional[str] = None,
    status: str = "EXITOSO",
    school_id: Optional[int] = None
) -> AuditLog:
    user_id = getattr(actor, "id", None)
    user_email = getattr(actor, "email", None)
    user_name = getattr(actor, "name", None)
    user_role = actor.role.name if (actor and getattr(actor, "role", None)) else None
    
    if not school_id and actor and getattr(actor, "school_id", None):
        school_id = actor.school_id

    entry = AuditLog(
        user_id=user_id,
        user_email=user_email,
        user_name=user_name,
        user_role=user_role,
        action=action,
        target_id=target_id,
        target_dni=target_dni,
        target_name=target_name,
        details=details,
        status=status,
        school_id=school_id
    )
    db.add(entry)
    try:
        db.commit()
        db.refresh(entry)
    except Exception as e:
        db.rollback()
        print(f"Error persisting audit log: {e}")
    return entry
