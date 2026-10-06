from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from .models import Tramite
from app.modules.academico.alumnos.models import Alumno
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

router = APIRouter(prefix="/oficina", tags=["Oficina de Alumnos"])

class TramiteCreate(BaseModel):
    alumno_id: int
    tipo_tramite: str
    observaciones: Optional[str] = None

class TramiteStatusUpdate(BaseModel):
    estado: str  # "Pendiente", "En Proceso", "Listo"
    observaciones: Optional[str] = None

@router.get("/tramites")
def listar_tramites(db: Session = Depends(get_db)):
    tramites = db.query(Tramite).all()
    res = []
    for t in tramites:
        res.append({
            "id": t.id,
            "alumno_id": t.alumno_id,
            "alumno_nombre": f"{t.alumno.nombre} {t.alumno.apellido}" if t.alumno else "Desconocido",
            "alumno_dni": t.alumno.dni if t.alumno else "Desconocido",
            "tipo_tramite": t.tipo_tramite,
            "fecha_solicitud": t.fecha_solicitud,
            "estado": t.estado,
            "observaciones": t.observaciones
        })
    return res

@router.post("/tramites")
def crear_tramite(data: TramiteCreate, db: Session = Depends(get_db)):
    alumno = db.query(Alumno).filter(Alumno.id == data.alumno_id).first()
    if not alumno:
        raise HTTPException(status_code=404, detail="Alumno no encontrado")
        
    tramite = Tramite(
        alumno_id=data.alumno_id,
        tipo_tramite=data.tipo_tramite,
        fecha_solicitud=datetime.now().strftime("%Y-%m-%d"),
        estado="Pendiente",
        observaciones=data.observaciones
    )
    db.add(tramite)
    db.commit()
    db.refresh(tramite)
    return tramite

@router.put("/tramites/{tramite_id}/estado")
def actualizar_estado_tramite(tramite_id: int, data: TramiteStatusUpdate, db: Session = Depends(get_db)):
    tramite = db.query(Tramite).filter(Tramite.id == tramite_id).first()
    if not tramite:
        raise HTTPException(status_code=404, detail="Trámite no encontrado")
        
    tramite.estado = data.estado
    if data.observaciones is not None:
        tramite.observaciones = data.observaciones
        
    db.commit()
    db.refresh(tramite)
    return tramite
