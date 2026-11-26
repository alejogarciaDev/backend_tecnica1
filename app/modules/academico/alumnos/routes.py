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
    dni: str
    nombre: str
    apellido: str
    folio: Optional[str] = None
    legajo: Optional[str] = None
    telefono: Optional[str] = None
    fecha_nacimiento: Optional[str] = None
    curso: Optional[str] = None
    division: Optional[str] = None
    turno: Optional[str] = None
    grupo_taller: Optional[str] = None
    estado: Optional[str] = "Activo"
    estado_academico: Optional[str] = "REGULAR"
    primaria_completa: Optional[bool] = False
    primaria_fecha: Optional[str] = None
    primaria_escuela: Optional[str] = None
    primaria_localidad: Optional[str] = None
    historial: list[HistorialCreate] = []
    familiares: list[FamiliarCreate] = []

@router.get("/")
def list_alumnos(anio: Optional[str] = None, tipo: Optional[str] = None, db: Session = Depends(get_db), current_user = Depends(get_current_user_db)):
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

def format_alumno_detail(alumno: Alumno, db: Session):
    user_obj = alumno.user
    if not user_obj and alumno.user_id:
        from app.modules.users.users.models import User
        user_obj = db.query(User).filter(User.id == alumno.user_id).first()
    if not user_obj and alumno.dni:
        from app.modules.users.users.models import User
        user_obj = db.query(User).filter(User.dni == alumno.dni).first()

    hist = []
    for h in (alumno.historial or []):
        hist.append({
            "id": h.id,
            "anio": h.anio,
            "curso": h.curso,
            "repitio": h.repitio,
            "observaciones": h.observaciones
        })

    fams = []
    for f in (alumno.familiares or []):
        fams.append({
            "id": f.id,
            "nombre": f.nombre,
            "apellido": f.apellido,
            "telefono": f.telefono,
            "relacion": f.relacion
        })

    curso_display = (alumno.curso or "").strip()
    if alumno.division:
        curso_display = f"{curso_display} {alumno.division}".strip()
    if not curso_display and hist:
        curso_display = hist[-1]["curso"]

    nom = alumno.nombre
    ape = alumno.apellido
    if (not nom or nom.strip() in ("", "null", "None")) and user_obj and user_obj.name:
        parts = user_obj.name.strip().split(" ", 1)
        nom = parts[0]
        ape = parts[1] if len(parts) > 1 else ""

    return {
        "id": alumno.id,
        "dni": alumno.dni or (user_obj.dni if user_obj else "") or "",
        "nombre": nom or "",
        "apellido": ape or "",
        "folio": alumno.folio or "",
        "legajo": alumno.legajo or "",
        "telefono": alumno.telefono or "",
        "fecha_nacimiento": alumno.fecha_nacimiento or (user_obj.fecha_nacimiento if user_obj else "") or "",
        "curso": alumno.curso or "",
        "division": alumno.division or "",
        "curso_division": curso_display,
        "turno": alumno.turno or "",
        "grupo_taller": alumno.grupo_taller or "",
        "estado": alumno.estado or "Activo",
        "estado_academico": alumno.estado_academico or "REGULAR",
        "primaria_completa": bool(alumno.primaria_completa),
        "primaria_fecha": alumno.primaria_fecha or "",
        "primaria_escuela": alumno.primaria_escuela or "",
        "primaria_localidad": alumno.primaria_localidad or "",
        "email": user_obj.email if user_obj else "",
        "domicilio": user_obj.domicilio if user_obj else "",
        "historial": hist,
        "familiares": fams,
        "user_id": alumno.user_id
    }

@router.get("/{dni}")
def get_alumno(dni: str, db: Session = Depends(get_db), current_user = Depends(get_current_user_db)):
    dni_clean = str(dni).strip()
    alumno = db.query(Alumno).filter((Alumno.dni == dni_clean) | (Alumno.dni == dni_clean.zfill(8))).first()
    if not alumno and dni_clean.isdigit():
        alumno = db.query(Alumno).filter(Alumno.id == int(dni_clean)).first()
    if not alumno:
        raise HTTPException(status_code=404, detail=f"No se encontró ningún alumno registrado con DNI o ID '{dni_clean}'")
    return format_alumno_detail(alumno, db)

@router.post("/")
def create_alumno(data: AlumnoCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user_db)):
    dni_clean = str(data.dni).strip()
    existing = db.query(Alumno).filter(Alumno.dni == dni_clean).first()
    
    estado_final = data.estado or ("Egresado" if data.estado_academico == "EGRESADO" else "Activo")
    estado_acad_final = data.estado_academico or ("EGRESADO" if estado_final.lower() == "egresado" else "REGULAR")
    
    if existing:
        existing.nombre = data.nombre
        existing.apellido = data.apellido
        if data.folio is not None: existing.folio = data.folio
        if data.legajo is not None: existing.legajo = data.legajo
        if data.telefono is not None: existing.telefono = data.telefono
        if data.fecha_nacimiento is not None: existing.fecha_nacimiento = data.fecha_nacimiento
        if data.curso is not None: existing.curso = data.curso
        if data.division is not None: existing.division = data.division
        if data.turno is not None: existing.turno = data.turno
        if data.grupo_taller is not None: existing.grupo_taller = data.grupo_taller
        if data.primaria_completa is not None: existing.primaria_completa = data.primaria_completa
        if data.primaria_fecha is not None: existing.primaria_fecha = data.primaria_fecha
        if data.primaria_escuela is not None: existing.primaria_escuela = data.primaria_escuela
        if data.primaria_localidad is not None: existing.primaria_localidad = data.primaria_localidad
        existing.estado = estado_final
        existing.estado_academico = estado_acad_final
        alumno = existing
    else:
        alumno = Alumno(
            dni=dni_clean,
            nombre=data.nombre,
            apellido=data.apellido,
            folio=data.folio,
            legajo=data.legajo,
            telefono=data.telefono,
            fecha_nacimiento=data.fecha_nacimiento,
            curso=data.curso,
            division=data.division,
            turno=data.turno,
            grupo_taller=data.grupo_taller,
            estado=estado_final,
            estado_academico=estado_acad_final,
            primaria_completa=data.primaria_completa or False,
            primaria_fecha=data.primaria_fecha,
            primaria_escuela=data.primaria_escuela,
            primaria_localidad=data.primaria_localidad
        )
        db.add(alumno)
        db.flush()
        
    for h in data.historial:
        db.add(AlumnoHistorial(alumno_id=alumno.id, anio=h.anio, curso=h.curso, repitio=h.repitio, observaciones=h.observaciones))
    for f in data.familiares:
        db.add(FamiliarTutor(alumno_id=alumno.id, nombre=f.nombre, apellido=f.apellido, telefono=f.telefono, relacion=f.relacion))
    db.commit()
    db.refresh(alumno)
    return format_alumno_detail(alumno, db)

class AlumnoUpdate(BaseModel):
    dni: Optional[str] = None
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    folio: Optional[str] = None
    legajo: Optional[str] = None
    telefono: Optional[str] = None
    fecha_nacimiento: Optional[str] = None
    curso: Optional[str] = None
    division: Optional[str] = None
    turno: Optional[str] = None
    grupo_taller: Optional[str] = None
    estado: Optional[str] = None
    estado_academico: Optional[str] = None
    primaria_completa: Optional[bool] = None
    primaria_fecha: Optional[str] = None
    primaria_escuela: Optional[str] = None
    primaria_localidad: Optional[str] = None
    email: Optional[str] = None
    domicilio: Optional[str] = None
    historial: Optional[list[HistorialCreate]] = None
    familiares: Optional[list[FamiliarCreate]] = None

@router.put("/{alumno_id}")
def update_alumno(alumno_id: str, data: AlumnoUpdate, db: Session = Depends(get_db), current_user = Depends(get_current_user_db)):
    ident_str = str(alumno_id).strip()
    alumno = None
    if ident_str.isdigit():
        alumno = db.query(Alumno).filter((Alumno.id == int(ident_str)) | (Alumno.dni == ident_str)).first()
    else:
        alumno = db.query(Alumno).filter(Alumno.dni == ident_str).first()

    if not alumno:
        raise HTTPException(status_code=404, detail="Alumno no encontrado")

    if data.dni is not None and data.dni.strip():
        new_dni = data.dni.strip()
        exist = db.query(Alumno).filter(Alumno.dni == new_dni, Alumno.id != alumno.id).first()
        if exist:
            raise HTTPException(status_code=400, detail=f"El DNI {new_dni} ya pertenece a otro alumno.")
        alumno.dni = new_dni

    if data.nombre is not None: alumno.nombre = data.nombre.strip()
    if data.apellido is not None: alumno.apellido = data.apellido.strip()
    if data.folio is not None: alumno.folio = data.folio.strip()
    if data.legajo is not None: alumno.legajo = data.legajo.strip()
    if data.telefono is not None: alumno.telefono = data.telefono.strip()
    if data.fecha_nacimiento is not None: alumno.fecha_nacimiento = data.fecha_nacimiento.strip()
    if data.curso is not None: alumno.curso = data.curso.strip()
    if data.division is not None: alumno.division = data.division.strip()
    if data.turno is not None: alumno.turno = data.turno.strip()
    if data.grupo_taller is not None: alumno.grupo_taller = data.grupo_taller.strip()
    if data.estado is not None: alumno.estado = data.estado.strip()
    if data.estado_academico is not None: alumno.estado_academico = data.estado_academico.strip()
    if data.primaria_completa is not None: alumno.primaria_completa = data.primaria_completa
    if data.primaria_fecha is not None: alumno.primaria_fecha = data.primaria_fecha.strip()
    if data.primaria_escuela is not None: alumno.primaria_escuela = data.primaria_escuela.strip()
    if data.primaria_localidad is not None: alumno.primaria_localidad = data.primaria_localidad.strip()

    # Sincronizar usuario vinculado si existe
    user_obj = alumno.user
    if not user_obj and alumno.user_id:
        from app.modules.users.users.models import User
        user_obj = db.query(User).filter(User.id == alumno.user_id).first()
    if not user_obj and alumno.dni:
        from app.modules.users.users.models import User
        user_obj = db.query(User).filter(User.dni == alumno.dni).first()

    if user_obj:
        if data.dni is not None and data.dni.strip():
            user_obj.dni = data.dni.strip()
        if data.nombre is not None or data.apellido is not None:
            user_obj.name = f"{alumno.nombre} {alumno.apellido}".strip()
        if data.email is not None and data.email.strip():
            user_obj.email = data.email.strip().lower()
        if data.domicilio is not None:
            user_obj.domicilio = data.domicilio.strip()
        if data.fecha_nacimiento is not None:
            user_obj.fecha_nacimiento = data.fecha_nacimiento.strip()

    if data.curso is not None:
        curso_full = f"{alumno.curso} {alumno.division or ''}".strip()
        hist = db.query(AlumnoHistorial).filter(AlumnoHistorial.alumno_id == alumno.id, AlumnoHistorial.anio == "2026").first()
        if hist:
            hist.curso = curso_full
        else:
            db.add(AlumnoHistorial(alumno_id=alumno.id, anio="2026", curso=curso_full))

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
    return format_alumno_detail(alumno, db)

@router.delete("/{alumno_id}")
def delete_alumno(alumno_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user_db)):
    alumno = db.query(Alumno).filter(Alumno.id == alumno_id).first()
    if alumno: db.delete(alumno); db.commit()
    return {"status": "ok"}

class AsignarCursoRequest(BaseModel):
    curso: str
    anio_lectivo: Optional[str] = "2026"

@router.post("/{alumno_id}/asignar-curso")
def asignar_curso(alumno_id: int, req: AsignarCursoRequest, db: Session = Depends(get_db), current_user = Depends(get_current_user_db)):
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
def set_grupo_taller(alumno_id: int, req: GrupoTallerRequest, db: Session = Depends(get_db), current_user = Depends(get_current_user_db)):
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
def importar_alumnos(req: AlumnosImportRequest, db: Session = Depends(get_db), current_user = Depends(get_current_user_db)):
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
