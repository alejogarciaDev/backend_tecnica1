from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List
from app.core.database import get_db
from app.core.security import get_current_user_db, require_permission
from . import schemas, service

router = APIRouter(prefix="/secretaria", tags=["Secretaría - Gestión de Alumnos"])

@router.post("/alumnos", response_model=schemas.AlumnoSecretariaOut)
def pre_registrar_alumno(
    data: schemas.AlumnoPreRegistro,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_db),
    _ = Depends(require_permission("secretaria.alumnos.create"))
):
    return service.pre_registrar_alumno(db, data, current_user)

@router.get("/alumnos", response_model=List[schemas.AlumnoSecretariaOut])
def list_alumnos_secretaria(
    q: Optional[str] = Query(None, description="Búsqueda por DNI, Nombre, Apellido o Legajo"),
    curso: Optional[str] = None,
    division: Optional[str] = None,
    turno: Optional[str] = None,
    estado_academico: Optional[str] = None,
    estado_cuenta: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_db),
    _ = Depends(require_permission("secretaria.alumnos.list"))
):
    school_id = getattr(current_user, "school_id", None)
    return service.get_alumnos_secretaria(
        db,
        q=q,
        curso=curso,
        division=division,
        turno=turno,
        estado_academico=estado_academico,
        estado_cuenta=estado_cuenta,
        school_id=school_id
    )

@router.get("/alumnos/{alumno_id}")
def get_alumno_ficha(
    alumno_id: int,
    db: Session = Depends(get_db),
    _ = Depends(require_permission("secretaria.alumnos.list"))
):
    return service.get_alumno_by_id(db, alumno_id)

@router.put("/alumnos/{alumno_id}")
def update_alumno(
    alumno_id: int,
    data: schemas.AlumnoUpdateSecretaria,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_db),
    _ = Depends(require_permission("secretaria.alumnos.edit"))
):
    return service.update_alumno(db, alumno_id, data, current_user)

@router.put("/alumnos/{alumno_id}/estado-academico")
def update_estado_academico(
    alumno_id: int,
    data: schemas.EstadoAcademicoUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_db),
    _ = Depends(require_permission("secretaria.alumnos.estado"))
):
    return service.update_estado_academico(db, alumno_id, data, current_user)

@router.put("/alumnos/{alumno_id}/bloqueo")
def update_bloqueo_cuenta(
    alumno_id: int,
    data: schemas.BloqueoCuentaUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_db),
    _ = Depends(require_permission("secretaria.alumnos.bloqueo"))
):
    return service.update_bloqueo_cuenta(db, alumno_id, data, current_user)

@router.post("/alumnos/{alumno_id}/reset-password")
def reset_password_alumno(
    alumno_id: int,
    data: schemas.ResetPasswordRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_db),
    _ = Depends(require_permission("secretaria.alumnos.password"))
):
    return service.reset_password_alumno(db, alumno_id, data, current_user)

@router.get("/metricas", response_model=schemas.SecretariaMetricas)
def get_metricas(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_db),
    _ = Depends(require_permission("secretaria.dashboard"))
):
    school_id = getattr(current_user, "school_id", None)
    return service.get_metricas_secretaria(db, school_id=school_id)

@router.get("/auditoria", response_model=List[schemas.AuditLogItem])
def get_auditoria(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_db),
    _ = Depends(require_permission("secretaria.auditoria"))
):
    school_id = getattr(current_user, "school_id", None)
    return service.get_auditoria_secretaria(db, limit=limit, school_id=school_id)
