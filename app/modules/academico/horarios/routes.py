from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from .models import Horario
from app.modules.academico.materias.models import Materia
from app.core.security import get_current_user_db
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/horarios", tags=["Académico - Horarios"])

class HorarioCreate(BaseModel):
    materia_id: int
    dia_semana: str
    hora_inicio: str
    hora_fin: str
    aula: Optional[str] = None

@router.get("/materia/{materia_id}")
def obtener_horario_materia(materia_id: int, db: Session = Depends(get_db)):
    return db.query(Horario).filter(Horario.materia_id == materia_id).all()

@router.get("/curso/{curso_nombre}")
def obtener_horario_curso(curso_nombre: str, db: Session = Depends(get_db)):
    horarios = db.query(Horario).join(Materia).filter(Materia.curso == curso_nombre).all()
    res = []
    for h in horarios:
        res.append({
            "id": h.id,
            "materia_id": h.materia_id,
            "materia_nombre": h.materia.nombre if h.materia else "Materia eliminada",
            "dia_semana": h.dia_semana,
            "hora_inicio": h.hora_inicio,
            "hora_fin": h.hora_fin,
            "aula": h.aula
        })
    return res

@router.post("/")
def crear_horario(data: HorarioCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user_db)):
    materia = db.query(Materia).filter(Materia.id == data.materia_id).first()
    if not materia:
        raise HTTPException(status_code=404, detail="Materia no encontrada")
        
    horario = Horario(
        materia_id=data.materia_id,
        dia_semana=data.dia_semana,
        hora_inicio=data.hora_inicio,
        hora_fin=data.hora_fin,
        aula=data.aula
    )
    db.add(horario)
    db.commit()
    db.refresh(horario)
    return horario

@router.delete("/{id}")
def eliminar_horario(id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user_db)):
    horario = db.query(Horario).filter(Horario.id == id).first()
    if not horario:
        raise HTTPException(status_code=404, detail="Horario no encontrado")
    db.delete(horario)
    db.commit()
    return {"status": "ok", "message": "Horario eliminado"}
