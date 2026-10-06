from fastapi import HTTPException
from app.core.security import get_current_user_db
from app.modules.users.roles.models import Role
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import require_permission
from . import service, schemas

router = APIRouter(prefix="/users", tags=["Users"])

@router.post("/", response_model=schemas.UserOut)
def create_user(
    data: schemas.UserCreate, 
    db: Session = Depends(get_db), 
    _ = Depends(require_permission("users.create")),
    current_user = Depends(get_current_user_db)
):
    target_role = db.query(Role).filter(Role.id == data.role_id).first()
    creator_role = (current_user.role.name if current_user.role else "").lower().strip()

    if target_role and target_role.name == "alumno":
        if creator_role == "admin":
            raise HTTPException(
                status_code=403,
                detail="No autorizado. El rol Administrador no puede crear alumnos. Los alumnos deben ser pre-registrados exclusivamente desde Secretaría."
            )

    if target_role and target_role.name in ("admin", "superadmin"):
        # Requiere que el creador sea superadmin
        if creator_role != "superadmin":
            raise HTTPException(
                status_code=403, 
                detail="No autorizado. Solo los Súper Administradores pueden crear usuarios administradores."
            )
            
    return service.create_user(db, data)

@router.get("/", response_model=list[schemas.UserOut])
def list_users(db: Session = Depends(get_db), _=Depends(require_permission("users.list"))):
    return service.get_users(db)

@router.get("/{user_id}", response_model=schemas.UserOut)
def get_user(user_id: int, db: Session = Depends(get_db), _=Depends(require_permission("users.list"))):
    return service.get_user_by_id(db, user_id)

@router.delete("/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), _=Depends(require_permission("users.delete"))):
    return service.delete_user(db, user_id)

@router.put("/{user_id}/role")
def change_role(
    user_id: int, 
    role_id: int, 
    db: Session = Depends(get_db), 
    _ = Depends(require_permission("users.change_role")),
    current_user = Depends(get_current_user_db)
):
    # Check if target role is admin or superadmin
    target_role = db.query(Role).filter(Role.id == role_id).first()
    if target_role and target_role.name in ("admin", "superadmin"):
        # Requiere que el emisor sea superadmin
        creator_role = current_user.role.name if current_user.role else ""
        if creator_role != "superadmin":
            raise HTTPException(
                status_code=403, 
                detail="No autorizado. Solo los Súper Administradores pueden asignar roles de administrador."
            )
            
    return service.change_role(db, user_id, role_id)

@router.put("/{user_id}", response_model=schemas.UserOut)
def update_user(user_id: int, data: schemas.UserUpdate, db: Session = Depends(get_db), _=Depends(require_permission("users.update"))):
    return service.update_user(db, user_id, data)
