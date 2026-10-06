from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.modules.academico.alumnos.models import Alumno, AlumnoHistorial
from app.modules.academico.calificaciones.models import CalificacionAcademica
from app.modules.academico.asistencias.models import Asistencia
from app.modules.academico.materias.models import Materia
from .models import BoletinPublicado
from app.core.security import get_current_user_db
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
from datetime import datetime, date
import json

router = APIRouter(prefix="/boletines", tags=["Académico - Boletines"])

class BoletinPrepararCreate(BaseModel):
    alumno_id: int
    curso: str
    anio_lectivo: str
    periodo: str
    observaciones: Optional[str] = None
    estado: Optional[str] = "borrador" # "borrador" or "publicado"
    contenido: Optional[Dict[str, Any]] = None

@router.get("/alumno/{alumno_id}/generar")
def generar_boletin_alumno(alumno_id: int, anio: Optional[str] = None, db: Session = Depends(get_db), current_user = Depends(get_current_user_db)):
    alumno = db.query(Alumno).filter(Alumno.id == alumno_id).first()
    if not alumno:
        raise HTTPException(status_code=404, detail="Alumno no encontrado")
        
    # Get course info
    if anio:
        latest_hist = db.query(AlumnoHistorial).filter(AlumnoHistorial.alumno_id == alumno_id, AlumnoHistorial.anio == anio).first()
    else:
        latest_hist = db.query(AlumnoHistorial).filter(AlumnoHistorial.alumno_id == alumno_id).order_by(AlumnoHistorial.anio.desc()).first()
        
    curso = latest_hist.curso if latest_hist else "Sin Asignar"
    anio_lectivo = latest_hist.anio if latest_hist else str(date.today().year)

    # Get subjects of this course
    subjects = db.query(Materia).filter(Materia.curso == curso).all()
    if not subjects:
        subjects = db.query(Materia).all()
        
    # Get approved grades
    grades = db.query(CalificacionAcademica).filter(
        CalificacionAcademica.alumno_id == alumno_id,
        CalificacionAcademica.aprobado_preceptor == True
    ).all()
    
    # Get absences
    asistencias = db.query(Asistencia).filter(Asistencia.alumno_id == alumno_id).all()
    total_inasistencias = sum(1 for a in asistencias if a.estado == "Ausente")
    tardes = sum(1 for a in asistencias if a.estado == "Tarde")
    
    # Structure grades by subject and period
    grades_by_subject: Dict[int, Dict[str, float]] = {}
    for g in grades:
        if g.materia_id not in grades_by_subject:
            grades_by_subject[g.materia_id] = {}
        grades_by_subject[g.materia_id][g.periodo] = g.nota
        
    materias_data = []
    for s in subjects:
        s_grades = grades_by_subject.get(s.id, {})
        n1 = s_grades.get("1° Trimestre")
        n2 = s_grades.get("2° Trimestre")
        n3 = s_grades.get("3° Trimestre")
        
        valid_notes = [n for n in [n1, n2, n3] if n is not None]
        promedio = round(sum(valid_notes) / len(valid_notes), 2) if valid_notes else None
        nota_final = s_grades.get("Final") or promedio
        
        materias_data.append({
            "materia_id": s.id,
            "materia_nombre": s.nombre,
            "profesor_nombre": f"{s.profesor.nombre} {s.profesor.apellido}" if s.profesor else "Sin asignar",
            "tipo": s.tipo,
            "notas": {
                "trimestre_1": n1,
                "trimestre_2": n2,
                "trimestre_3": n3,
                "final": nota_final
            }
        })
        
    return {
        "alumno": {
            "id": alumno.id,
            "nombre": f"{alumno.nombre} {alumno.apellido}",
            "legajo": alumno.legajo or "",
            "folio": alumno.folio or "",
            "dni": alumno.dni,
            "curso": curso,
            "anio_lectivo": anio_lectivo
        },
        "materias": materias_data,
        "asistencias": {
            "ausentes": total_inasistencias,
            "tardes": tardes
        }
    }

# ==============================================================================
# GESTIÓN Y PUBLICACIÓN DE BOLETINES (Preceptor & Admin)
# ==============================================================================

@router.get("/curso/{curso_nombre}/alumnos")
def listar_boletines_curso(curso_nombre: str, db: Session = Depends(get_db), current_user = Depends(get_current_user_db)):
    # Buscar alumnos cuyo historial más reciente corresponda a este curso
    historiales = db.query(AlumnoHistorial).filter(AlumnoHistorial.curso == curso_nombre).all()
    alumnos_ids = list(set([h.alumno_id for h in historiales]))
    alumnos = db.query(Alumno).filter(Alumno.id.in_(alumnos_ids)).all() if alumnos_ids else []

    res = []
    for al in alumnos:
        # Buscar si ya tiene boletín preparado/publicado
        boletin_rec = db.query(BoletinPublicado).filter(
            BoletinPublicado.alumno_id == al.id,
            BoletinPublicado.curso == curso_nombre
        ).order_by(BoletinPublicado.id.desc()).first()

        estado = boletin_rec.estado if boletin_rec else "sin_preparar"
        fecha_pub = str(boletin_rec.fecha_publicacion) if (boletin_rec and boletin_rec.fecha_publicacion) else None

        res.append({
            "alumno_id": al.id,
            "alumno_nombre": f"{al.nombre} {al.apellido}",
            "alumno_dni": al.dni,
            "legajo": al.legajo or "",
            "curso": curso_nombre,
            "boletin_id": boletin_rec.id if boletin_rec else None,
            "estado": estado,
            "fecha_publicacion": fecha_pub,
            "observaciones": boletin_rec.observaciones if boletin_rec else ""
        })

    return res

@router.post("/preparar")
def preparar_boletin(data: BoletinPrepararCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user_db)):
    alumno = db.query(Alumno).filter(Alumno.id == data.alumno_id).first()
    if not alumno:
        raise HTTPException(status_code=404, detail="Alumno no encontrado")

    # Si no se pasó contenido_json, generarlo automáticamente con notas y asistencias
    contenido = data.contenido
    if not contenido:
        contenido = generar_boletin_alumno(alumno_id=data.alumno_id, anio=data.anio_lectivo, db=db, current_user=current_user)

    contenido_str = json.dumps(contenido)

    # Buscar si ya existe boletín para este periodo y curso
    existente = db.query(BoletinPublicado).filter(
        BoletinPublicado.alumno_id == data.alumno_id,
        BoletinPublicado.curso == data.curso,
        BoletinPublicado.periodo == data.periodo,
        BoletinPublicado.anio_lectivo == data.anio_lectivo
    ).first()

    es_publicado = data.estado == "publicado"
    fecha_pub = datetime.utcnow() if es_publicado else None

    if existente:
        existente.observaciones = data.observaciones or existente.observaciones
        existente.contenido_json = contenido_str
        existente.estado = data.estado or "borrador"
        if es_publicado:
            existente.fecha_publicacion = fecha_pub
            existente.publicado_por_id = current_user.id
        db.commit()
        db.refresh(existente)
        return {"message": "Boletín actualizado", "id": existente.id, "estado": existente.estado}

    nuevo = BoletinPublicado(
        alumno_id=data.alumno_id,
        curso=data.curso,
        anio_lectivo=data.anio_lectivo,
        periodo=data.periodo,
        estado=data.estado or "borrador",
        fecha_publicacion=fecha_pub,
        publicado_por_id=current_user.id if es_publicado else None,
        observaciones=data.observaciones or "",
        contenido_json=contenido_str
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return {"message": "Boletín preparado correctamente", "id": nuevo.id, "estado": nuevo.estado}

@router.post("/{id}/publicar")
def publicar_boletin(id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user_db)):
    bol = db.query(BoletinPublicado).filter(BoletinPublicado.id == id).first()
    if not bol:
        raise HTTPException(status_code=404, detail="Boletín no encontrado")

    bol.estado = "publicado"
    bol.fecha_publicacion = datetime.utcnow()
    bol.publicado_por_id = current_user.id
    db.commit()
    return {"message": "Boletín publicado con éxito"}

@router.post("/{id}/despublicar")
def despublicar_boletin(id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user_db)):
    bol = db.query(BoletinPublicado).filter(BoletinPublicado.id == id).first()
    if not bol:
        raise HTTPException(status_code=404, detail="Boletín no encontrado")

    bol.estado = "borrador"
    db.commit()
    return {"message": "Boletín devuelto a borrador"}

@router.post("/curso/{curso_nombre}/publicar-todos")
def publicar_todos_los_boletines_curso(curso_nombre: str, db: Session = Depends(get_db), current_user = Depends(get_current_user_db)):
    boletines = db.query(BoletinPublicado).filter(
        BoletinPublicado.curso == curso_nombre,
        BoletinPublicado.estado == "borrador"
    ).all()

    now = datetime.utcnow()
    for b in boletines:
        b.estado = "publicado"
        b.fecha_publicacion = now
        b.publicado_por_id = current_user.id

    db.commit()
    return {"message": f"Se han publicado {len(boletines)} boletines para el curso {curso_nombre}"}

@router.get("/alumno/{alumno_id}/publicados")
def boletines_publicados_alumno(alumno_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user_db)):
    boletines = db.query(BoletinPublicado).filter(
        BoletinPublicado.alumno_id == alumno_id,
        BoletinPublicado.estado == "publicado"
    ).order_by(BoletinPublicado.fecha_publicacion.desc()).all()

    res = []
    for b in boletines:
        try:
            content = json.loads(b.contenido_json)
        except Exception:
            content = {}
        res.append({
            "id": b.id,
            "curso": b.curso,
            "anio_lectivo": b.anio_lectivo,
            "periodo": b.periodo,
            "fecha_publicacion": str(b.fecha_publicacion) if b.fecha_publicacion else "",
            "observaciones": b.observaciones or "",
            "contenido": content
        })
    return res
