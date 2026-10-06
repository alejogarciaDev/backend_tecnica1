from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from .models import Profesor
from app.modules.academico.materias.models import Materia
from pydantic import BaseModel
from typing import Optional, List
from app.core.security import get_current_user_db

router = APIRouter(prefix="/profesores", tags=["Profesores"])

class ProfesorCreate(BaseModel):
    dni: str
    nombre: str
    apellido: str
    especialidad: Optional[str] = None
    telefono: Optional[str] = None
    tipo: Optional[str] = "aula" # "aula" or "taller"
    user_id: Optional[int] = None

class AssignMaterias(BaseModel):
    materia_ids: List[int]

@router.get("/me")
def obtener_mi_perfil(db: Session = Depends(get_db), current_user = Depends(get_current_user_db)):
    profesor = db.query(Profesor).filter(Profesor.user_id == current_user.id).first()
    if not profesor:
        raise HTTPException(status_code=404, detail="El usuario no tiene un perfil de profesor asociado")
    return {
        "id": profesor.id,
        "dni": profesor.dni,
        "nombre": profesor.nombre,
        "apellido": profesor.apellido,
        "especialidad": profesor.especialidad,
        "telefono": profesor.telefono,
        "tipo": profesor.tipo,
        "user_id": profesor.user_id
    }

@router.get("/")
def listar_profesores(db: Session = Depends(get_db)):
    profesores = db.query(Profesor).all()
    res = []
    for p in profesores:
        res.append({
            "id": p.id,
            "dni": p.dni,
            "nombre": p.nombre,
            "apellido": p.apellido,
            "especialidad": p.especialidad,
            "telefono": p.telefono,
            "tipo": p.tipo,
            "user_id": p.user_id,
            "materias": [{"id": m.id, "nombre": m.nombre} for m in p.materias]
        })
    return res

@router.post("/")
def crear_profesor(data: ProfesorCreate, db: Session = Depends(get_db)):
    existing = db.query(Profesor).filter(Profesor.dni == data.dni).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe un profesor con ese DNI")
        
    profesor = Profesor(
        dni=data.dni,
        nombre=data.nombre,
        apellido=data.apellido,
        especialidad=data.especialidad,
        telefono=data.telefono,
        tipo=data.tipo or "aula",
        user_id=data.user_id
    )
    db.add(profesor)
    db.commit()
    db.refresh(profesor)
    return profesor

@router.put("/{profesor_id}/materias")
def asignar_materias(profesor_id: int, data: AssignMaterias, db: Session = Depends(get_db)):
    profesor = db.query(Profesor).filter(Profesor.id == profesor_id).first()
    if not profesor:
        raise HTTPException(status_code=404, detail="Profesor no encontrado")
        
    # Clear existing associations for this professor
    for m in profesor.materias:
        m.profesor_id = None
        
    # Associate new ones
    materias = db.query(Materia).filter(Materia.id.in_(data.materia_ids)).all()
    for m in materias:
        m.profesor_id = profesor.id
        
    db.commit()
    db.refresh(profesor)
    return {
        "status": "ok",
        "message": f"Materias asignadas al profesor {profesor.nombre} {profesor.apellido}",
        "materias": [{"id": m.id, "nombre": m.nombre} for m in profesor.materias]
    }
