from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from .models import Asistencia
from app.modules.academico.alumnos.models import Alumno
from pydantic import BaseModel
from typing import List, Optional
from datetime import date
from app.core.security import get_current_user_db

router = APIRouter(prefix="/asistencias", tags=["Académico - Asistencias"])

class AsistenciaItem(BaseModel):
    alumno_id: int
    estado: str # Presente, Ausente, Tarde

class AsistenciaLote(BaseModel):
    fecha: date
    turno: str # Mañana, Tarde, Taller
    items: List[AsistenciaItem]

@router.post("/lote")
def registrar_asistencia_lote(data: AsistenciaLote, db: Session = Depends(get_db), current_user = Depends(get_current_user_db)):
    for item in data.items:
        existing = db.query(Asistencia).filter(
            Asistencia.alumno_id == item.alumno_id,
            Asistencia.fecha == data.fecha,
            Asistencia.turno == data.turno
        ).first()
        
        if existing:
            existing.estado = item.estado
            existing.registrado_por_id = current_user.id
        else:
            asistencia = Asistencia(
                alumno_id=item.alumno_id,
                fecha=data.fecha,
                turno=data.turno,
                estado=item.estado,
                registrado_por_id=current_user.id
            )
            db.add(asistencia)
            
    db.commit()
    return {"status": "ok", "message": f"Se registraron {len(data.items)} asistencias."}

@router.get("/curso/{curso_nombre}")
def obtener_asistencias_curso(curso_nombre: str, db: Session = Depends(get_db)):
    from app.modules.academico.alumnos.models import AlumnoHistorial
    alumnos = db.query(Alumno).join(AlumnoHistorial).filter(AlumnoHistorial.curso == curso_nombre).all()
    alumno_ids = [a.id for a in alumnos]
    
    asistencias = db.query(Asistencia).filter(Asistencia.alumno_id.in_(alumno_ids)).all() if alumno_ids else []
    
    res_students = []
    for a in alumnos:
        sa = sorted([x for x in asistencias if x.alumno_id == a.id], key=lambda x: x.fecha, reverse=True)
        
        absences = sum(1 for x in sa if x.estado == "Ausente")
        
        consecutive = 0
        for x in sa:
            if x.estado == "Ausente":
                consecutive += 1
            else:
                break
                
        res_students.append({
            "id": a.id,
            "name": f"{a.nombre} {a.apellido}",
            "nombre": a.nombre,
            "apellido": a.apellido,
            "dni": a.dni,
            "legajo": a.legajo,
            "grupo_taller": a.grupo_taller,
            "absences": absences,
            "consecutive_absences": consecutive,
            "history": [{
                "id": x.id,
                "fecha": str(x.fecha),
                "turno": x.turno,
                "estado": x.estado
            } for x in sa]
        })
        
    return res_students

class AsistenciaJustificarRequest(BaseModel):
    alumno_id: int
    fecha: str
    turno: str
    estado: str

@router.post("/justificar")
def justificar_asistencia(data: AsistenciaJustificarRequest, db: Session = Depends(get_db), current_user = Depends(get_current_user_db)):
    import datetime
    try:
        fecha_date = datetime.datetime.strptime(data.fecha, "%Y-%m-%d").date()
    except Exception:
        raise HTTPException(status_code=400, detail="Formato de fecha inválido. Usar YYYY-MM-DD")
        
    asistencia = db.query(Asistencia).filter(
        Asistencia.alumno_id == data.alumno_id,
        Asistencia.fecha == fecha_date,
        Asistencia.turno == data.turno
    ).first()
    
    if asistencia:
        asistencia.estado = data.estado
    else:
        asistencia = Asistencia(
            alumno_id=data.alumno_id,
            fecha=fecha_date,
            turno=data.turno,
            estado=data.estado,
            registrado_por_id=current_user.id
        )
        db.add(asistencia)
    db.commit()
    db.refresh(asistencia)
    return {"status": "ok", "asistencia": {"id": asistencia.id, "estado": asistencia.estado}}
