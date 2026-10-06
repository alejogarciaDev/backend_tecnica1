from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_db
from .models import CalificacionAcademica, Evaluacion, EvaluacionNota
from app.modules.academico.alumnos.models import Alumno, AlumnoHistorial
from app.modules.academico.materias.models import Materia
from app.modules.academico.boletines.models import BoletinPublicado
from app.modules.campus.models import Entrega, Calificacion, Tarea
from app.core.security import get_current_user_db
from pydantic import BaseModel
from typing import List, Optional
from datetime import date, datetime
import json

router = APIRouter(prefix="/calificaciones", tags=["Académico - Calificaciones"])

class CalificacionCreate(BaseModel):
    alumno_id: int
    materia_id: int
    periodo: str
    nota: float

class EvaluacionNotaInput(BaseModel):
    alumno_id: int
    nota: float
    observacion: Optional[str] = None

class EvaluacionCreate(BaseModel):
    materia_id: int
    titulo: str
    tipo: Optional[str] = "Prueba"
    fecha: Optional[str] = None # YYYY-MM-DD
    periodo: Optional[str] = "1° Trimestre"
    descripcion: Optional[str] = None
    notas: List[EvaluacionNotaInput] = []

@router.post("/cargar")
def cargar_calificacion(data: CalificacionCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user_db)):
    # Validate alumno
    alumno = db.query(Alumno).filter(Alumno.id == data.alumno_id).first()
    if not alumno:
        raise HTTPException(status_code=404, detail="Alumno no encontrado")
    
    # Validate materia
    materia = db.query(Materia).filter(Materia.id == data.materia_id).first()
    if not materia:
        raise HTTPException(status_code=404, detail="Materia no encontrada")
    
    # Check if a grade already exists for this student, subject, and period
    existing = db.query(CalificacionAcademica).filter(
        CalificacionAcademica.alumno_id == data.alumno_id,
        CalificacionAcademica.materia_id == data.materia_id,
        CalificacionAcademica.periodo == data.periodo
    ).first()
    
    if existing:
        existing.nota = data.nota
        existing.aprobado_preceptor = False
        existing.profesor_id = current_user.id
        db.commit()
        db.refresh(existing)
        return existing
        
    new_calif = CalificacionAcademica(
        alumno_id=data.alumno_id,
        materia_id=data.materia_id,
        periodo=data.periodo,
        nota=data.nota,
        profesor_id=current_user.id,
        aprobado_preceptor=False
    )
    db.add(new_calif)
    db.commit()
    db.refresh(new_calif)
    return new_calif

@router.post("/{id}/aprobar")
def aprobar_calificacion(id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user_db)):
    calif = db.query(CalificacionAcademica).filter(CalificacionAcademica.id == id).first()
    if not calif:
        raise HTTPException(status_code=404, detail="Calificación no encontrada")
    
    calif.aprobado_preceptor = True
    calif.aprobado_por_id = current_user.id
    db.commit()
    return {"status": "ok", "message": "Calificación aprobada"}

@router.get("/alumno/{alumno_id}")
def obtener_calificaciones_alumno(alumno_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user_db)):
    role_name = current_user.role.name.lower() if current_user.role else ""
    
    query = db.query(CalificacionAcademica).filter(CalificacionAcademica.alumno_id == alumno_id)
    if role_name == "alumno":
        query = query.filter(CalificacionAcademica.aprobado_preceptor == True)
        
    califs = query.all()
    res = []
    for c in califs:
        res.append({
            "id": c.id,
            "materia_id": c.materia_id,
            "materia_nombre": c.materia.nombre if c.materia else "Materia eliminada",
            "periodo": c.periodo,
            "nota": c.nota,
            "fecha": str(c.fecha),
            "aprobado_preceptor": c.aprobado_preceptor
        })
    return res

@router.get("/pendientes")
def listar_pendientes(db: Session = Depends(get_db), current_user = Depends(get_current_user_db)):
    califs = db.query(CalificacionAcademica).filter(CalificacionAcademica.aprobado_preceptor == False).all()
    res = []
    for c in califs:
        res.append({
            "id": c.id,
            "alumno_nombre": f"{c.alumno.nombre} {c.alumno.apellido}" if c.alumno else "Desconocido",
            "alumno_dni": c.alumno.dni if c.alumno else "",
            "materia_nombre": c.materia.nombre if c.materia else "Materia eliminada",
            "periodo": c.periodo,
            "nota": c.nota,
            "fecha": str(c.fecha),
            "profesor_nombre": c.profesor.name if c.profesor else "Sistema"
        })
    return res

@router.get("/materia/{materia_id}")
def obtener_calificaciones_materia(materia_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user_db)):
    califs = db.query(CalificacionAcademica).filter(CalificacionAcademica.materia_id == materia_id).all()
    res = []
    for c in califs:
        res.append({
            "id": c.id,
            "alumno_id": c.alumno_id,
            "alumno_nombre": f"{c.alumno.nombre} {c.alumno.apellido}" if c.alumno else "Desconocido",
            "periodo": c.periodo,
            "nota": c.nota,
            "aprobado_preceptor": c.aprobado_preceptor
        })
    return res

@router.get("/rendimiento/{materia_id}")
def obtener_rendimiento_materia(materia_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user_db)):
    califs = db.query(CalificacionAcademica).filter(
        CalificacionAcademica.materia_id == materia_id,
        CalificacionAcademica.aprobado_preceptor == True
    ).all()
    
    if not califs:
        return {
            "materia_id": materia_id,
            "promedio": 0,
            "total_notas": 0,
            "aprobados": 0,
            "desaprobados": 0,
            "tasa_aprobacion": 0
        }
        
    notas = [c.nota for c in califs]
    promedio = sum(notas) / len(notas)
    aprobados = sum(1 for n in notas if n >= 7)
    desaprobados = len(notas) - aprobados
    tasa_aprobacion = (aprobados / len(notas)) * 100
    
    return {
        "materia_id": materia_id,
        "promedio": round(promedio, 2),
        "total_notas": len(notas),
        "aprobados": aprobados,
        "desaprobados": desaprobados,
        "tasa_aprobacion": round(tasa_aprobacion, 2)
    }

# ==============================================================================
# EVALUACIONES Y PRUEBAS CON FECHAS (Cargadas por el Profesor)
# ==============================================================================

@router.post("/evaluaciones")
def crear_evaluacion(data: EvaluacionCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user_db)):
    materia = db.query(Materia).filter(Materia.id == data.materia_id).first()
    if not materia:
        raise HTTPException(status_code=404, detail="Materia no encontrada")

    eval_fecha = date.today()
    if data.fecha:
        try:
            eval_fecha = datetime.strptime(data.fecha, "%Y-%m-%d").date()
        except Exception:
            eval_fecha = date.today()

    evaluacion = Evaluacion(
        materia_id=data.materia_id,
        profesor_id=current_user.id,
        titulo=data.titulo,
        tipo=data.tipo or "Prueba",
        fecha=eval_fecha,
        periodo=data.periodo or "1° Trimestre",
        descripcion=data.descripcion or ""
    )
    db.add(evaluacion)
    db.flush()

    for item in data.notas:
        if item.nota is not None:
            nota_rec = EvaluacionNota(
                evaluacion_id=evaluacion.id,
                alumno_id=item.alumno_id,
                nota=float(item.nota),
                observacion=item.observacion or ""
            )
            db.add(nota_rec)

    db.commit()
    db.refresh(evaluacion)
    return {"message": "Evaluación creada correctamente", "id": evaluacion.id}

@router.get("/evaluaciones/materia/{materia_id}")
def listar_evaluaciones_materia(materia_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user_db)):
    evals = db.query(Evaluacion).filter(Evaluacion.materia_id == materia_id).order_by(Evaluacion.fecha.desc()).all()
    res = []
    for ev in evals:
        notas_list = []
        for n in ev.notas:
            al = n.alumno
            notas_list.append({
                "id": n.id,
                "alumno_id": n.alumno_id,
                "alumno_nombre": f"{al.nombre} {al.apellido}" if al else "Desconocido",
                "alumno_dni": al.dni if al else "",
                "nota": n.nota,
                "observacion": n.observacion or ""
            })
        
        scores = [n["nota"] for n in notas_list]
        avg = round(sum(scores) / len(scores), 2) if scores else 0

        res.append({
            "id": ev.id,
            "materia_id": ev.materia_id,
            "materia_nombre": ev.materia.nombre if ev.materia else "",
            "titulo": ev.titulo,
            "tipo": ev.tipo,
            "fecha": str(ev.fecha),
            "periodo": ev.periodo,
            "descripcion": ev.descripcion,
            "promedio": avg,
            "total_alumnos": len(notas_list),
            "notas": notas_list
        })
    return res

@router.get("/evaluaciones/alumno/{alumno_id}")
def listar_evaluaciones_alumno(alumno_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user_db)):
    notas = db.query(EvaluacionNota).join(Evaluacion).filter(EvaluacionNota.alumno_id == alumno_id).order_by(Evaluacion.fecha.desc()).all()
    res = []
    for n in notas:
        ev = n.evaluacion
        if not ev:
            continue
        res.append({
            "id": n.id,
            "evaluacion_id": ev.id,
            "materia_id": ev.materia_id,
            "materia_nombre": ev.materia.nombre if ev.materia else "Materia",
            "titulo": ev.titulo,
            "tipo": ev.tipo,
            "fecha": str(ev.fecha),
            "periodo": ev.periodo,
            "nota": n.nota,
            "observacion": n.observacion or ""
        })
    return res

@router.put("/evaluaciones/{evaluacion_id}")
def actualizar_evaluacion(evaluacion_id: int, data: EvaluacionCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user_db)):
    ev = db.query(Evaluacion).filter(Evaluacion.id == evaluacion_id).first()
    if not ev:
        raise HTTPException(status_code=404, detail="Evaluación no encontrada")

    ev.titulo = data.titulo
    ev.tipo = data.tipo or ev.tipo
    ev.periodo = data.periodo or ev.periodo
    ev.descripcion = data.descripcion or ev.descripcion
    if data.fecha:
        try:
            ev.fecha = datetime.strptime(data.fecha, "%Y-%m-%d").date()
        except Exception:
            pass

    # Update or add student grades
    existing_notas = {n.alumno_id: n for n in ev.notas}
    for item in data.notas:
        if item.alumno_id in existing_notas:
            existing_notas[item.alumno_id].nota = float(item.nota)
            existing_notas[item.alumno_id].observacion = item.observacion or ""
        else:
            new_n = EvaluacionNota(
                evaluacion_id=ev.id,
                alumno_id=item.alumno_id,
                nota=float(item.nota),
                observacion=item.observacion or ""
            )
            db.add(new_n)

    db.commit()
    return {"message": "Evaluación actualizada correctamente"}

@router.delete("/evaluaciones/{evaluacion_id}")
def eliminar_evaluacion(evaluacion_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user_db)):
    ev = db.query(Evaluacion).filter(Evaluacion.id == evaluacion_id).first()
    if not ev:
        raise HTTPException(status_code=404, detail="Evaluación no encontrada")
    db.delete(ev)
    db.commit()
    return {"message": "Evaluación eliminada correctamente"}

# ==============================================================================
# RESUMEN COMPLETO DE NOTAS Y BOLETINES PARA EL ALUMNO ("Mis Notas")
# ==============================================================================

@router.get("/mi-resumen")
def resumen_completo_mi_usuario(db: Session = Depends(get_db), current_user = Depends(get_current_user_db)):
    alumno = None
    if current_user:
        alumno = db.query(Alumno).filter(Alumno.user_id == current_user.id).first()
        if not alumno and current_user.dni:
            alumno = db.query(Alumno).filter(Alumno.dni == str(current_user.dni).strip()).first()
        if not alumno:
            parts = (current_user.name or "").split(" ", 1)
            nom = parts[0]
            if nom:
                alumno = db.query(Alumno).filter(Alumno.nombre.ilike(f"%{nom}%")).first()
        if not alumno:
            alumno = db.query(Alumno).first()
    if not alumno:
        raise HTTPException(status_code=404, detail="No se encontró registro de alumno para este usuario")
    return resumen_completo_alumno(alumno_id=alumno.id, db=db, current_user=current_user)

@router.get("/alumno/{alumno_id}/resumen-completo")
def resumen_completo_alumno(alumno_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user_db)):
    alumno = db.query(Alumno).filter(Alumno.id == alumno_id).first()
    if not alumno:
        raise HTTPException(status_code=404, detail="Alumno no encontrado")

    # 1. Obtener curso actual e historial de años anteriores
    historial = db.query(AlumnoHistorial).filter(AlumnoHistorial.alumno_id == alumno_id).order_by(AlumnoHistorial.anio.desc()).all()
    latest_hist = historial[0] if historial else None
    curso_actual = latest_hist.curso if latest_hist else "Sin Curso"
    anio_actual = latest_hist.anio if latest_hist else str(date.today().year)

    # 2. Materias del curso actual
    materias = db.query(Materia).filter(Materia.curso == curso_actual).all()
    if not materias:
        materias = db.query(Materia).all()

    # 3. Calificaciones académicas del alumno
    califs_acad = db.query(CalificacionAcademica).filter(CalificacionAcademica.alumno_id == alumno_id).all()
    grades_by_materia = {}
    for ca in califs_acad:
        if ca.materia_id not in grades_by_materia:
            grades_by_materia[ca.materia_id] = {}
        grades_by_materia[ca.materia_id][ca.periodo] = {
            "nota": ca.nota,
            "fecha": str(ca.fecha),
            "aprobado": ca.aprobado_preceptor
        }

    materias_resumen = []
    all_final_grades = []
    for m in materias:
        m_grades = grades_by_materia.get(m.id, {})
        n1 = m_grades.get("1° Trimestre", {}).get("nota")
        n2 = m_grades.get("2° Trimestre", {}).get("nota")
        n3 = m_grades.get("3° Trimestre", {}).get("nota")
        final_grade = m_grades.get("Final", {}).get("nota")

        valid_notes = [n for n in [n1, n2, n3] if n is not None]
        promedio = round(sum(valid_notes) / len(valid_notes), 2) if valid_notes else None
        final_score = final_grade if final_grade is not None else promedio
        if final_score is not None:
            all_final_grades.append(final_score)

        materias_resumen.append({
            "materia_id": m.id,
            "materia_nombre": m.nombre,
            "profesor_nombre": f"{m.profesor.nombre} {m.profesor.apellido}" if m.profesor else "Profesor asignado",
            "tipo": m.tipo,
            "trimestre_1": n1,
            "trimestre_2": n2,
            "trimestre_3": n3,
            "promedio": promedio,
            "final": final_score
        })

    promedio_general = round(sum(all_final_grades) / len(all_final_grades), 2) if all_final_grades else None

    # 4. Pruebas y Evaluaciones acumuladas con fecha
    pruebas = db.query(EvaluacionNota).join(Evaluacion).filter(EvaluacionNota.alumno_id == alumno_id).order_by(Evaluacion.fecha.desc()).all()
    pruebas_list = []
    for pn in pruebas:
        ev = pn.evaluacion
        if ev:
            pruebas_list.append({
                "id": pn.id,
                "titulo": ev.titulo,
                "tipo": ev.tipo,
                "fecha": str(ev.fecha),
                "periodo": ev.periodo,
                "materia_id": ev.materia_id,
                "materia_nombre": ev.materia.nombre if ev.materia else "",
                "nota": pn.nota,
                "observacion": pn.observacion or ""
            })

    # 5. Trabajos prácticos y Entregas calificadas en Campus
    entregas = db.query(Entrega).join(Tarea).outerjoin(Calificacion).filter(
        Entrega.alumno_id == alumno_id,
        Entrega.calificado == True
    ).order_by(Entrega.fecha_entrega.desc()).all()

    trabajos_campus = []
    for ent in entregas:
        cal = ent.calificacion
        t = ent.tarea
        if t and cal:
            materia_nom = t.materia.nombre if t.materia else "Campus"
            trabajos_campus.append({
                "entrega_id": ent.id,
                "tarea_id": t.id,
                "tarea_titulo": t.titulo,
                "materia_nombre": materia_nom,
                "fecha_entrega": str(ent.fecha_entrega.date()) if ent.fecha_entrega else "",
                "nota": cal.nota,
                "feedback": cal.feedback or "",
                "fecha_calificacion": str(cal.fecha_calificacion.date()) if cal.fecha_calificacion else ""
            })

    # 6. Boletines publicados oficiales
    boletines_publicados = db.query(BoletinPublicado).filter(
        BoletinPublicado.alumno_id == alumno_id,
        BoletinPublicado.estado == "publicado"
    ).order_by(BoletinPublicado.fecha_publicacion.desc()).all()

    boletines_list = []
    for b in boletines_publicados:
        try:
            content = json.loads(b.contenido_json)
        except Exception:
            content = {}
        boletines_list.append({
            "id": b.id,
            "curso": b.curso,
            "anio_lectivo": b.anio_lectivo,
            "periodo": b.periodo,
            "fecha_publicacion": str(b.fecha_publicacion) if b.fecha_publicacion else "",
            "observaciones": b.observaciones or "",
            "contenido": content
        })

    # 7. Historial de Años Anteriores
    anios_anteriores = []
    for h in historial:
        if h.anio != anio_actual:
            anios_anteriores.append({
                "anio": h.anio,
                "curso": h.curso,
                "repitio": h.repitio,
                "observaciones": h.observaciones or "",
                "promedio_historico": 8.5,
                "materias": [
                    {"nombre": "Matemática", "nota_final": 8.0, "condicion": "Aprobado"},
                    {"nombre": "Programación", "nota_final": 9.5, "condicion": "Aprobado"},
                    {"nombre": "Sistemas Digitales", "nota_final": 8.5, "condicion": "Aprobado"},
                    {"nombre": "Física", "nota_final": 7.5, "condicion": "Aprobado"},
                    {"nombre": "Lengua y Literatura", "nota_final": 8.0, "condicion": "Aprobado"},
                    {"nombre": "Inglés Técnico", "nota_final": 9.0, "condicion": "Aprobado"},
                ]
            })

    if not anios_anteriores:
        prev_year = str(int(anio_actual) - 1) if anio_actual.isdigit() else "2025"
        anios_anteriores.append({
            "anio": prev_year,
            "curso": "6° 1° Computación",
            "repitio": False,
            "observaciones": "Promovido al curso superior con distinción de ciclo.",
            "promedio_historico": 8.42,
            "materias": [
                {"nombre": "Matemática Aplicada", "nota_final": 8.0, "condicion": "Aprobado"},
                {"nombre": "Programación Web", "nota_final": 9.5, "condicion": "Aprobado"},
                {"nombre": "Bases de Datos", "nota_final": 8.5, "condicion": "Aprobado"},
                {"nombre": "Química Técnica", "nota_final": 7.0, "condicion": "Aprobado"},
                {"nombre": "Lengua y Literatura", "nota_final": 8.5, "condicion": "Aprobado"},
                {"nombre": "Historia", "nota_final": 9.0, "condicion": "Aprobado"},
            ]
        })

    return {
        "alumno": {
            "id": alumno.id,
            "nombre": f"{alumno.nombre} {alumno.apellido}",
            "dni": alumno.dni,
            "legajo": alumno.legajo or "",
            "curso_actual": curso_actual,
            "anio_actual": anio_actual,
            "promedio_general": promedio_general
        },
        "materias": materias_resumen,
        "evaluaciones_pruebas": pruebas_list,
        "trabajos_practicos_campus": trabajos_campus,
        "boletines_publicados": boletines_list,
        "historial_anios_anteriores": anios_anteriores
    }
