from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import require_permission
from . import service, schemas

router = APIRouter(prefix="/roles", tags=["Roles"])

@router.post("/", response_model=schemas.RoleOut)
def create_role(data: schemas.RoleCreate, db: Session = Depends(get_db), _=Depends(require_permission("roles.create"))):
    return service.create_role(db, data)

@router.get("/", response_model=list[schemas.RoleOut])
def list_roles(db: Session = Depends(get_db)):
    return service.get_roles(db)

@router.delete("/{role_id}")
def delete_role(role_id: int, db: Session = Depends(get_db), _=Depends(require_permission("roles.delete"))):
    return service.delete_role(db, role_id)
