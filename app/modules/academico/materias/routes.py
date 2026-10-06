from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from .models import Materia
from pydantic import BaseModel
from typing import Optional
from app.modules.profesores.models import Profesor

router = APIRouter(prefix="/materias", tags=["Académico - Materias"])

class MateriaCreate(BaseModel):
    nombre: str
    descripcion: Optional[str] = None
    curso: Optional[str] = None
    tipo: Optional[str] = "aula" # "aula" or "taller"
    profesor_id: Optional[int] = None

class MateriaUpdate(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    curso: Optional[str] = None
    tipo: Optional[str] = None # "aula" or "taller"
    profesor_id: Optional[int] = None

@router.get("/cursos")
def list_cursos(db: Session = Depends(get_db)):
    from app.modules.academico.alumnos.models import AlumnoHistorial
    c1 = db.query(Materia.curso).distinct().all()
    c2 = db.query(AlumnoHistorial.curso).distinct().all()
    cursos = set([x[0] for x in c1 if x[0]] + [x[0] for x in c2 if x[0]])
    if not list(cursos):
        cursos = {"1er año", "2do año", "3er año", "4to año", "5to año", "6to año", "7mo año"}
    return sorted(list(cursos))

from app.core.security import get_current_user_db

@router.get("/")
def list_materias(curso: Optional[str] = None, db: Session = Depends(get_db), current_user = Depends(get_current_user_db)):
    query = db.query(Materia)
    if curso: 
        query = query.filter(Materia.curso == curso)
    
    role_name = current_user.role.name if current_user.role else ""
    if role_name == "profesor":
        profesor = db.query(Profesor).filter(
            (Profesor.user_id == current_user.id) |
            ((Profesor.dni == current_user.dni) & (Profesor.dni != None) & (Profesor.dni != ""))
        ).first()
        if profesor:
            if not profesor.user_id:
                profesor.user_id = current_user.id
                db.commit()
            mats = query.filter(Materia.profesor_id == profesor.id).all()
            if mats:
                return mats
            return db.query(Materia).all()
        else:
            return db.query(Materia).all()
    elif role_name == "alumno":
        from app.modules.academico.alumnos.models import Alumno, AlumnoHistorial
        alumno = db.query(Alumno).filter(
            (Alumno.user_id == current_user.id) |
            ((Alumno.dni == current_user.dni) & (Alumno.dni != None) & (Alumno.dni != "")) |
            ((Alumno.correo_electronico == current_user.email) & (Alumno.correo_electronico != None))
        ).first()
        if alumno:
            if not alumno.user_id:
                alumno.user_id = current_user.id
                db.commit()
            latest_historial = db.query(AlumnoHistorial).filter(AlumnoHistorial.alumno_id == alumno.id).order_by(AlumnoHistorial.anio.desc()).first()
            if latest_historial and latest_historial.curso:
                c_nombre = latest_historial.curso
                digits = [c for c in c_nombre if c.isdigit()]
                first_digit = digits[0] if digits else ""
                if first_digit:
                    query = query.filter(
                        (Materia.curso == c_nombre) |
                        (Materia.curso.like(f"{first_digit}%")) |
                        (Materia.curso.like(f"%{c_nombre}%"))
                    )
                else:
                    query = query.filter(Materia.curso == c_nombre)
                mats = query.all()
                if mats:
                    return mats
                return db.query(Materia).all()
            else:
                return db.query(Materia).all()
        else:
            return db.query(Materia).all()
            
    return query.all()

def validar_profesor_materia(profesor_id: Optional[int], materia_tipo: str, db: Session):
    if profesor_id:
        prof = db.query(Profesor).filter(Profesor.id == profesor_id).first()
        if not prof:
            raise HTTPException(status_code=404, detail="Profesor no encontrado")
        if prof.tipo == "aula" and materia_tipo == "taller":
            raise HTTPException(
                status_code=400,
                detail="Un profesor de tipo aula no puede dictar materias de tipo taller"
            )

@router.post("/")
def create_materia(data: MateriaCreate, db: Session = Depends(get_db)):
    materia_tipo = data.tipo or "aula"
    validar_profesor_materia(data.profesor_id, materia_tipo, db)
    
    # Check if the course name indicates a standard year group rather than a specific division
    standard_year_match = None
    curso_lower = data.curso.lower()
    if "año" in curso_lower:
        if "1er" in curso_lower or "1" in curso_lower: standard_year_match = "1"
        elif "2do" in curso_lower or "2" in curso_lower: standard_year_match = "2"
        elif "3er" in curso_lower or "3" in curso_lower: standard_year_match = "3"
        elif "4to" in curso_lower or "4" in curso_lower: standard_year_match = "4"
        elif "5to" in curso_lower or "5" in curso_lower: standard_year_match = "5"
        elif "6to" in curso_lower or "6" in curso_lower: standard_year_match = "6"
        elif "7mo" in curso_lower or "7" in curso_lower: standard_year_match = "7"

    if standard_year_match:
        from app.modules.academico.cursos.models import Curso
        # Fetch all courses where anio starts with standard_year_match or matches it
        courses_to_add = db.query(Curso).filter(
            (Curso.anio == standard_year_match) | 
            (Curso.anio.like(f"{standard_year_match}%")) |
            (Curso.nombre.like(f"{standard_year_match}%"))
        ).all()
        
        created_materias = []
        for c in courses_to_add:
            # Check if this subject already exists in this course to avoid duplicate
            exists = db.query(Materia).filter(
                Materia.nombre == data.nombre,
                Materia.curso == c.nombre
            ).first()
            if not exists:
                m = Materia(
                    nombre=data.nombre,
                    descripcion=data.descripcion,
                    curso=c.nombre,
                    tipo=materia_tipo,
                    profesor_id=data.profesor_id
                )
                db.add(m)
                created_materias.append(m)
        db.commit()
        for m in created_materias:
            db.refresh(m)
        return created_materias[0] if created_materias else {"status": "ok", "message": "No new courses found or subjects already existed"}
    else:
        materia = Materia(
            nombre=data.nombre,
            descripcion=data.descripcion,
            curso=data.curso,
            tipo=materia_tipo,
            profesor_id=data.profesor_id
        )
        db.add(materia); db.commit(); db.refresh(materia)
        return materia

@router.put("/{materia_id}")
def update_materia(materia_id: int, data: MateriaUpdate, db: Session = Depends(get_db)):
    materia = db.query(Materia).filter(Materia.id == materia_id).first()
    if not materia:
        raise HTTPException(status_code=404, detail="Materia no encontrada")
        
    materia_tipo = data.tipo if data.tipo is not None else materia.tipo
    profesor_id = data.profesor_id if data.profesor_id is not None else materia.profesor_id
    if profesor_id == 0:
        profesor_id = None
        
    validar_profesor_materia(profesor_id, materia_tipo, db)
    
    if data.nombre is not None:
        materia.nombre = data.nombre
    if data.descripcion is not None:
        materia.descripcion = data.descripcion
    if data.curso is not None:
        materia.curso = data.curso
    if data.tipo is not None:
        materia.tipo = data.tipo
    if data.profesor_id is not None:
        materia.profesor_id = profesor_id
        
    db.commit()
    db.refresh(materia)
    return materia

@router.delete("/{materia_id}")
def delete_materia(materia_id: int, db: Session = Depends(get_db)):
    materia = db.query(Materia).filter(Materia.id == materia_id).first()
    if materia: db.delete(materia); db.commit()
    return {"status": "ok"}
