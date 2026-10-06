from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user_db
from .models import Alumno, AlumnoHistorial, FamiliarTutor
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/alumnos", tags=["Académico - Alumnos"])

@router.get("/me")
def get_current_student_profile(db: Session = Depends(get_db), current_user = Depends(get_current_user_db)):
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
        raise HTTPException(status_code=404, detail="Perfil de alumno no encontrado")

    latest_hist = alumno.historial[-1] if (alumno.historial and len(alumno.historial) > 0) else None
    return {
        "id": alumno.id,
        "nombre": alumno.nombre,
        "apellido": alumno.apellido,
        "dni": alumno.dni,
        "legajo": alumno.legajo or "",
        "curso": latest_hist.curso if latest_hist else "1° 1°",
        "anio": latest_hist.anio if latest_hist else "2026"
    }

class HistorialCreate(BaseModel):
    anio: str; curso: str; repitio: bool = False; observaciones: Optional[str] = None

class FamiliarCreate(BaseModel):
    nombre: str
    apellido: str
    telefono: str
    relacion: str

class AlumnoCreate(BaseModel):
    dni: str; nombre: str; apellido: str; folio: Optional[str] = None; legajo: Optional[str] = None
    telefono: Optional[str] = None
    historial: list[HistorialCreate] = []
    familiares: list[FamiliarCreate] = []

@router.get("/")
def list_alumnos(anio: Optional[str] = None, tipo: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Alumno)
    
    if anio:
        if tipo == "egresado":
            query = query.filter(Alumno.estado == "Egresado").join(Alumno.historial).filter(AlumnoHistorial.anio == anio)
        elif tipo == "ingresante":
            min_sub = db.query(
                AlumnoHistorial.alumno_id,
                func.min(AlumnoHistorial.anio).label("min_anio")
            ).group_by(AlumnoHistorial.alumno_id).subquery()
            query = query.join(min_sub, Alumno.id == min_sub.c.alumno_id).filter(min_sub.c.min_anio == anio)
        else:
            query = query.join(Alumno.historial).filter(AlumnoHistorial.anio == anio)
    else:
        if tipo == "egresado":
            query = query.filter(Alumno.estado == "Egresado")
        elif tipo == "ingresante":
            pass

    alumnos = query.distinct().all()
    from app.modules.users.users.models import User
    import urllib.request
    import json

    # 1. Sincronizar desde Supabase la tabla 'alumnos' (nombre_completo, apellido, dni, correo_electronico)
    supa_by_dni = {}
    supa_by_email = {}
    try:
        supa_url = "https://ajqcibpkafteyckevkbu.supabase.co/rest/v1/alumnos?select=*"
        supa_key = "sb_publishable_pd_GawxP4O9WZzdYWGINwA_YVbXlW4Z"
        req = urllib.request.Request(supa_url, headers={"apikey": supa_key, "Authorization": f"Bearer {supa_key}"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            supa_alumnos = json.loads(resp.read().decode())
            for sa in supa_alumnos:
                if sa.get("dni"):
                    supa_by_dni[str(sa.get("dni")).strip()] = sa
                if sa.get("correo_electronico"):
                    supa_by_email[str(sa.get("correo_electronico")).strip().lower()] = sa
    except Exception as e:
        pass

    non_student_roles = {
        'superadmin', 'admin', 'administrador', 'oficina_alumnos', 'oficina de alumnos',
        'ofalumnos', 'profesor', 'profesores', 'docente', 'preceptor', 'panol', 'panolero',
        'bibliotecario', 'biblioteca'
    }
    res = []
    for a in alumnos:
        user_obj = a.user
        if not user_obj and a.user_id:
            user_obj = db.query(User).filter(User.id == a.user_id).first()
        if not user_obj and a.dni:
            user_obj = db.query(User).filter(User.dni == a.dni).first()

        # Si el usuario vinculado tiene un rol que no sea 'alumno', limpiar el registro y omitirlo
        if user_obj and user_obj.role and user_obj.role.name:
            r_name = str(user_obj.role.name).strip().lower()
            if r_name != "alumno" or r_name in non_student_roles:
                try:
                    db.delete(a)
                    db.commit()
                except Exception:
                    db.rollback()
                continue

        # Buscar coincidencia en Supabase
        sa = None
        if a.dni and str(a.dni).strip() in supa_by_dni:
            sa = supa_by_dni[str(a.dni).strip()]
        elif user_obj and user_obj.email and user_obj.email.strip().lower() in supa_by_email:
            sa = supa_by_email[user_obj.email.strip().lower()]

        if sa:
            s_nom = (sa.get("nombre_completo") or sa.get("nombre") or "").strip()
            s_ape = (sa.get("apellido") or "").strip()
            s_dni = (sa.get("dni") or "").strip()
            if s_nom and (not a.nombre or str(a.nombre).strip() in ("", "null", "None")):
                a.nombre = s_nom
                if s_ape:
                    a.apellido = s_ape
            if s_dni and (not a.dni or str(a.dni).strip() in ("", "null", "None")):
                a.dni = s_dni
            if user_obj and not a.user_id:
                a.user_id = user_obj.id
            db.commit()

        if user_obj:
            if (not a.dni or str(a.dni).strip() in ("", "null", "None")) and user_obj.dni:
                a.dni = user_obj.dni
                db.commit()
            if (not a.nombre or str(a.nombre).strip() in ("", "null", "None")) and user_obj.name:
                parts = user_obj.name.strip().split(" ", 1)
                a.nombre = parts[0]
                a.apellido = parts[1] if len(parts) > 1 else ""
                db.commit()

        final_nom = a.nombre
        final_ape = a.apellido
        if (not final_nom or str(final_nom).strip() in ("", "null", "None")) and user_obj and user_obj.name:
            parts = user_obj.name.strip().split(" ", 1)
            final_nom = parts[0]
            final_ape = parts[1] if len(parts) > 1 else ""

        if not final_nom or str(final_nom).strip() in ("", "null", "None"):
            if user_obj and user_obj.email:
                final_nom = user_obj.email.split("@")[0].capitalize()
                final_ape = ""
            elif a.dni:
                final_nom = f"Alumno DNI {a.dni}"
                final_ape = ""
            else:
                continue

        # Skip dummy empty rows without DNI and name
        if final_nom == "Alumno" and not a.dni:
            continue

        hist = []
        for h in (a.historial or []):
            hist.append({
                "id": h.id,
                "alumno_id": h.alumno_id,
                "anio": h.anio,
                "curso": h.curso,
                "repitio": h.repitio,
                "observaciones": h.observaciones
            })

        fams = []
        for f in (a.familiares or []):
            fams.append({
                "id": f.id,
                "nombre": f.nombre,
                "apellido": f.apellido,
                "telefono": f.telefono,
                "relacion": f.relacion
            })
            
        res.append({
            "id": a.id,
            "dni": a.dni or (user_obj.dni if user_obj else "") or "",
            "nombre": final_nom,
            "apellido": final_ape or "",
            "folio": a.folio or "",
            "legajo": a.legajo or "",
            "grupo_taller": a.grupo_taller,
            "school_id": a.school_id,
            "user_id": a.user_id,
            "estado": a.estado or "Activo",
            "telefono": a.telefono or "",
            "historial": hist,
            "familiares": fams,
            "user": {
                "id": user_obj.id,
                "name": user_obj.name,
                "email": user_obj.email,
                "dni": user_obj.dni
            } if user_obj else None
        })
    return res

@router.get("/{dni}")
def get_alumno(dni: str, db: Session = Depends(get_db)):
    return db.query(Alumno).filter(Alumno.dni == dni).first()

@router.post("/")
def create_alumno(data: AlumnoCreate, db: Session = Depends(get_db)):
    alumno = Alumno(dni=data.dni, nombre=data.nombre, apellido=data.apellido, folio=data.folio, legajo=data.legajo, telefono=data.telefono)
    db.add(alumno); db.flush()
    for h in data.historial:
        db.add(AlumnoHistorial(alumno_id=alumno.id, anio=h.anio, curso=h.curso, repitio=h.repitio, observaciones=h.observaciones))
    for f in data.familiares:
        db.add(FamiliarTutor(alumno_id=alumno.id, nombre=f.nombre, apellido=f.apellido, telefono=f.telefono, relacion=f.relacion))
    db.commit(); db.refresh(alumno)
    return alumno

class AlumnoUpdate(BaseModel):
    dni: Optional[str] = None
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    folio: Optional[str] = None
    legajo: Optional[str] = None
    telefono: Optional[str] = None
    historial: Optional[list[HistorialCreate]] = None
    familiares: Optional[list[FamiliarCreate]] = None

@router.put("/{alumno_id}")
def update_alumno(alumno_id: int, data: AlumnoUpdate, db: Session = Depends(get_db)):
    alumno = db.query(Alumno).filter(Alumno.id == alumno_id).first()
    if not alumno:
        return {"error": "Alumno no encontrado"}
    if data.dni is not None:
        alumno.dni = data.dni
    if data.nombre is not None:
        alumno.nombre = data.nombre
    if data.apellido is not None:
        alumno.apellido = data.apellido
    if data.folio is not None:
        alumno.folio = data.folio
    if data.legajo is not None:
        alumno.legajo = data.legajo
    if data.telefono is not None:
        alumno.telefono = data.telefono
    if data.historial is not None:
        db.query(AlumnoHistorial).filter(AlumnoHistorial.alumno_id == alumno.id).delete()
        for h in data.historial:
            db.add(AlumnoHistorial(alumno_id=alumno.id, anio=h.anio, curso=h.curso, repitio=h.repitio, observaciones=h.observaciones))
    if data.familiares is not None:
        db.query(FamiliarTutor).filter(FamiliarTutor.alumno_id == alumno.id).delete()
        for f in data.familiares:
            db.add(FamiliarTutor(alumno_id=alumno.id, nombre=f.nombre, apellido=f.apellido, telefono=f.telefono, relacion=f.relacion))
    db.commit()
    db.refresh(alumno)
    return alumno

@router.delete("/{alumno_id}")
def delete_alumno(alumno_id: int, db: Session = Depends(get_db)):
    alumno = db.query(Alumno).filter(Alumno.id == alumno_id).first()
    if alumno: db.delete(alumno); db.commit()
    return {"status": "ok"}

class AsignarCursoRequest(BaseModel):
    curso: str
    anio_lectivo: Optional[str] = "2026"

@router.post("/{alumno_id}/asignar-curso")
def asignar_curso(alumno_id: int, req: AsignarCursoRequest, db: Session = Depends(get_db)):
    alumno = db.query(Alumno).filter(Alumno.id == alumno_id).first()
    if not alumno:
        raise HTTPException(status_code=404, detail="Alumno no encontrado")
    
    # We update or insert historial for the specified academic year
    hist = db.query(AlumnoHistorial).filter(
        AlumnoHistorial.alumno_id == alumno_id,
        AlumnoHistorial.anio == req.anio_lectivo
    ).first()
    
    if hist:
        hist.curso = req.curso
    else:
        hist = AlumnoHistorial(
            alumno_id=alumno_id,
            anio=req.anio_lectivo,
            curso=req.curso
        )
        db.add(hist)
    db.commit()
    return {"status": "ok", "curso": req.curso}

class GrupoTallerRequest(BaseModel):
    grupo_taller: Optional[str] = None

@router.post("/{alumno_id}/grupo-taller")
def set_grupo_taller(alumno_id: int, req: GrupoTallerRequest, db: Session = Depends(get_db)):
    alumno = db.query(Alumno).filter(Alumno.id == alumno_id).first()
    if not alumno:
        raise HTTPException(status_code=404, detail="Alumno no encontrado")
    alumno.grupo_taller = req.grupo_taller
    db.commit()
    return {"status": "ok", "grupo_taller": req.grupo_taller}

class AlumnoImportItem(BaseModel):
    dni: str
    nombre: str
    apellido: str
    legajo: Optional[str] = None
    folio: Optional[str] = None
    curso: Optional[str] = None
    anio_lectivo: Optional[str] = "2026"

class AlumnosImportRequest(BaseModel):
    alumnos: list[AlumnoImportItem]

@router.post("/importar")
def importar_alumnos(req: AlumnosImportRequest, db: Session = Depends(get_db)):
    imported = 0
    errors = []
    for item in req.alumnos:
        try:
            # Check if alumno exists
            existing = db.query(Alumno).filter(Alumno.dni == item.dni).first()
            if existing:
                existing.nombre = item.nombre
                existing.apellido = item.apellido
                if item.legajo: existing.legajo = item.legajo
                if item.folio: existing.folio = item.folio
                alumno = existing
            else:
                alumno = Alumno(
                    dni=item.dni,
                    nombre=item.nombre,
                    apellido=item.apellido,
                    legajo=item.legajo,
                    folio=item.folio,
                    estado="Activo"
                )
                db.add(alumno)
                db.flush()
                
            if item.curso:
                hist = db.query(AlumnoHistorial).filter(
                    AlumnoHistorial.alumno_id == alumno.id,
                    AlumnoHistorial.anio == item.anio_lectivo
                ).first()
                if hist:
                    hist.curso = item.curso
                else:
                    hist = AlumnoHistorial(
                        alumno_id=alumno.id,
                        anio=item.anio_lectivo,
                        curso=item.curso
                    )
                    db.add(hist)
            imported += 1
        except Exception as e:
            errors.append(f"Error importando DNI {item.dni}: {str(e)}")
            
    db.commit()
    return {"status": "ok", "imported": imported, "errors": errors}
