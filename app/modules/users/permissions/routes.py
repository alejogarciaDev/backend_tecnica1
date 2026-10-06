from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import require_permission
from . import service, schemas

router = APIRouter(prefix="/permissions", tags=["Permissions"])

@router.post("/", response_model=schemas.PermissionOut)
def create_permission(data: schemas.PermissionCreate, db: Session = Depends(get_db), _=Depends(require_permission("permissions.create"))):
    return service.create_permission(db, data)

@router.get("/", response_model=list[schemas.PermissionOut])
def list_permissions(db: Session = Depends(get_db)):
    return service.get_permissions(db)

@router.post("/assign")
def assign_permissions(data: schemas.AssignPermissions, db: Session = Depends(get_db), _=Depends(require_permission("permissions.assign"))):
    return service.assign_permissions(db, data)
