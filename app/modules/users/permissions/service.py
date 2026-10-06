from sqlalchemy.orm import Session
from .models import Permission
from . import schemas

def get_permissions(db: Session):
    return db.query(Permission).all()

def create_permission(db: Session, data: schemas.PermissionCreate):
    perm = Permission(name=data.name)
    db.add(perm)
    db.commit()
    db.refresh(perm)
    return perm

def assign_permissions(db: Session, data: schemas.AssignPermissions):
    perms = db.query(Permission).filter(Permission.id.in_(data.permission_ids)).all()
    if data.role_id:
        from ..roles.models import Role
        role = db.query(Role).filter(Role.id == data.role_id).first()
        if role:
            role.permissions = perms
    if data.user_id:
        from ..users.models import User
        user = db.query(User).filter(User.id == data.user_id).first()
        if user:
            user.permissions = perms
    db.commit()
    return {"status": "ok", "assigned": len(perms)}
