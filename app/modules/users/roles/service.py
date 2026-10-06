from sqlalchemy.orm import Session
from .models import Role
from . import schemas

def get_roles(db: Session):
    return db.query(Role).all()

def create_role(db: Session, data: schemas.RoleCreate):
    role = Role(name=data.name)
    db.add(role)
    db.commit()
    db.refresh(role)
    return role

def delete_role(db: Session, role_id: int):
    role = db.query(Role).filter(Role.id == role_id).first()
    if role:
        db.delete(role)
        db.commit()
    return role
