from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from .models import Curso
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter(prefix="/cursos", tags=["Académico - Cursos"])

class CursoCreate(BaseModel):
    nombre: Optional[str] = None
    turno: str
    anio: Optional[str] = None
    division: Optional[str] = None
    preceptor_principal_id: Optional[int] = None

class CursoUpdate(BaseModel):
    nombre: Optional[str] = None
    turno: Optional[str] = None
    anio: Optional[str] = None
    division: Optional[str] = None
    preceptor_principal_id: Optional[int] = None

@router.get("/")
def list_cursos(db: Session = Depends(get_db)):
    cursos = db.query(Curso).all()
    res = []
    for c in cursos:
        preceptor_name = None
        if c.preceptor_principal:
            preceptor_name = c.preceptor_principal.name
        res.append({
            "id": c.id,
            "nombre": c.nombre,
            "turno": c.turno,
            "anio": c.anio,
            "division": c.division,
            "preceptor_principal_id": c.preceptor_principal_id,
            "preceptor_principal_name": preceptor_name
        })
    return res

@router.post("/")
def create_curso(data: CursoCreate, db: Session = Depends(get_db)):
    nombre = data.nombre
    if not nombre and data.anio and data.division:
        nombre = f"{data.anio} {data.division}"
    if not nombre:
        raise HTTPException(status_code=400, detail="Debe especificar nombre o anio y division")
        
    existing = db.query(Curso).filter(Curso.nombre == nombre).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe un curso con ese nombre")
    
    curso = Curso(
        nombre=nombre,
        turno=data.turno,
        anio=data.anio,
        division=data.division,
        preceptor_principal_id=data.preceptor_principal_id
    )
    db.add(curso)
    db.commit()
    db.refresh(curso)
    return curso

@router.put("/{curso_id}")
def update_curso(curso_id: int, data: CursoUpdate, db: Session = Depends(get_db)):
    curso = db.query(Curso).filter(Curso.id == curso_id).first()
    if not curso:
        raise HTTPException(status_code=404, detail="Curso no encontrado")
    
    if data.anio is not None:
        curso.anio = data.anio
    if data.division is not None:
        curso.division = data.division
        
    if data.nombre is not None:
        existing = db.query(Curso).filter(Curso.nombre == data.nombre, Curso.id != curso_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Ya existe otro curso con ese nombre")
        curso.nombre = data.nombre
    elif (data.anio is not None or data.division is not None):
        # recalculate name if updated through year/division
        new_anio = data.anio if data.anio is not None else curso.anio
        new_div = data.division if data.division is not None else curso.division
        if new_anio and new_div:
            curso.nombre = f"{new_anio} {new_div}"
            
    if data.turno is not None:
        curso.turno = data.turno
    if data.preceptor_principal_id is not None:
        curso.preceptor_principal_id = data.preceptor_principal_id if data.preceptor_principal_id != 0 else None
        
    db.commit()
    db.refresh(curso)
    return curso
