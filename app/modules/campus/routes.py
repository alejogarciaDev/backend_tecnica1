from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from .models import Tarea, Entrega, Calificacion, MaterialEstudio
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/campus", tags=["Campus Virtual"])

from app.core.security import get_current_user_db
from datetime import datetime

class TareaCreate(BaseModel):
    materia_id: int
    titulo: str
    descripcion: Optional[str] = None
    fecha_limite: Optional[str] = None
    archivo_id: Optional[int] = None
    tipo: Optional[str] = "tarea" # 'tarea' | 'material'

class TareaUpdate(BaseModel):
    titulo: Optional[str] = None
    descripcion: Optional[str] = None
    fecha_limite: Optional[str] = None
    activa: Optional[bool] = None
    archivo_id: Optional[int] = None
    tipo: Optional[str] = None

@router.get("/tareas")
def list_tareas(materia_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(Tarea)
    if materia_id: query = query.filter(Tarea.materia_id == materia_id)
    return query.order_by(Tarea.created_at.desc()).all()

@router.put("/tareas/{tarea_id}")
def update_tarea(
    tarea_id: int,
    data: TareaUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_db)
):
    tarea = db.query(Tarea).filter(Tarea.id == tarea_id).first()
    if not tarea:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    if data.titulo is not None:
        tarea.titulo = data.titulo
    if data.descripcion is not None:
        tarea.descripcion = data.descripcion
    if data.activa is not None:
        tarea.activa = data.activa
    if data.archivo_id is not None:
        tarea.archivo_id = data.archivo_id
    if data.tipo is not None:
        tarea.tipo = data.tipo
    if data.fecha_limite is not None:
        try:
            tarea.fecha_limite = datetime.fromisoformat(data.fecha_limite) if data.fecha_limite else None
        except Exception:
            pass
    db.commit()
    db.refresh(tarea)
    return tarea

@router.post("/tareas")
def create_tarea(data: TareaCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user_db)):
    limite = None
    if data.fecha_limite:
        try:
            limite = datetime.fromisoformat(data.fecha_limite)
        except Exception:
            pass
            
    tarea = Tarea(
        materia_id=data.materia_id,
        profesor_id=current_user.id,
        titulo=data.titulo,
        descripcion=data.descripcion,
        fecha_limite=limite,
        archivo_id=data.archivo_id,
        tipo=data.tipo or "tarea"
    )
    db.add(tarea); db.commit(); db.refresh(tarea)
    
    # Generate system notifications for all students of this course
    try:
        from app.modules.academico.materias.models import Materia
        from app.modules.academico.alumnos.models import AlumnoHistorial, Alumno
        from app.modules.notifications.models import Notification
        
        materia = db.query(Materia).filter(Materia.id == data.materia_id).first()
        if materia and materia.curso:
            historiales = db.query(AlumnoHistorial).filter(AlumnoHistorial.curso == materia.curso).all()
            alumno_ids = [h.alumno_id for h in historiales]
            if alumno_ids:
                alumnos = db.query(Alumno).filter(Alumno.id.in_(alumno_ids)).all()
                is_mat = (data.tipo == "material")
                notif_title = f"Nuevo material en {materia.nombre}" if is_mat else f"Nueva tarea en {materia.nombre}"
                notif_msg = f"El profesor compartió material de estudio: {data.titulo}" if is_mat else f"El profesor publicó la tarea: {data.titulo}"
                for a in alumnos:
                    if a.user_id:
                        notif = Notification(
                            user_id=a.user_id,
                            title=notif_title,
                            message=notif_msg,
                            type="material" if is_mat else "tarea"
                        )
                        db.add(notif)
                db.commit()
    except Exception as e:
        print(f"Error al generar notificaciones: {e}")
        
    return tarea

@router.get("/entregas")
def list_entregas(tarea_id: Optional[int] = None, alumno_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(Entrega)
    if tarea_id: query = query.filter(Entrega.tarea_id == tarea_id)
    if alumno_id: query = query.filter(Entrega.alumno_id == alumno_id)
    return query.all()

from app.core.security import get_current_user_db

class EntregaCreate(BaseModel):
    tarea_id: int
    comentario: Optional[str] = None
    archivo_id: Optional[int] = None

@router.post("/entregas")
def create_entrega(data: EntregaCreate, db: Session = Depends(get_db), user=Depends(get_current_user_db)):
    from app.modules.academico.alumnos.models import Alumno
    alumno = db.query(Alumno).filter(Alumno.user_id == user.id).first()
    alumno_id = alumno.id if alumno else 1
    
    # Delete existing submission for this homework by this student if any
    old_entrega = db.query(Entrega).filter(Entrega.tarea_id == data.tarea_id, Entrega.alumno_id == alumno_id).first()
    if old_entrega:
        db.delete(old_entrega)
        db.flush()

    entrega = Entrega(
        tarea_id=data.tarea_id, 
        alumno_id=alumno_id, 
        comentario=data.comentario,
        archivo_id=data.archivo_id
    )
    db.add(entrega)
    db.commit()
    db.refresh(entrega)
    
    # Notify teacher about the submission
    try:
        from app.modules.notifications.models import Notification
        tarea = db.query(Tarea).filter(Tarea.id == data.tarea_id).first()
        if tarea and tarea.profesor_id:
            notif = Notification(
                user_id=tarea.profesor_id,
                title=f"Entrega de tarea en {tarea.materia.nombre if tarea.materia else ''}",
                message=f"El alumno {alumno.nombre if alumno else ''} {alumno.apellido if alumno else ''} entregó la tarea: {tarea.titulo}",
                type="tarea"
            )
            db.add(notif)
            db.commit()
    except Exception as e:
        print(f"Error notifying teacher: {e}")
        
    return entrega

@router.get("/entregas/tarea/{tarea_id}")
def get_entregas_by_tarea(tarea_id: int, db: Session = Depends(get_db)):
    tarea = db.query(Tarea).filter(Tarea.id == tarea_id).first()
    if not tarea:
        return {"error": "Tarea no encontrada"}
        
    # Get all students enrolled in the same course as this tarea's materia
    from app.modules.academico.materias.models import Materia
    from app.modules.academico.alumnos.models import Alumno, AlumnoHistorial
    
    materia = db.query(Materia).filter(Materia.id == tarea.materia_id).first()
    if not materia or not materia.curso:
        # Fallback to all students if no course or materia found
        alumnos = db.query(Alumno).all()
    else:
        # Filter students who are currently in this course (using their latest AlumnoHistorial)
        historiales = db.query(AlumnoHistorial).filter(AlumnoHistorial.curso == materia.curso).all()
        alumno_ids = [h.alumno_id for h in historiales]
        alumnos = db.query(Alumno).filter(Alumno.id.in_(alumno_ids)).all() if alumno_ids else []

    entregas = db.query(Entrega).filter(Entrega.tarea_id == tarea_id).all()
    entregas_map = {e.alumno_id: e for e in entregas}
    
    result = []
    for a in alumnos:
        entrega = entregas_map.get(a.id)
        calif = entrega.calificacion if entrega else None
        archivo = entrega.archivo if entrega else None
        tiene_archivo = entrega is not None and entrega.archivo_id is not None
        tiene_comentario = entrega is not None and bool(entrega.comentario and entrega.comentario.strip())
        esta_entregado = entrega is not None and (tiene_archivo or tiene_comentario)

        result.append({
            "alumno_id": a.id,
            "nombre": f"{a.nombre} {a.apellido}",
            "dni": a.dni,
            "entregado": esta_entregado,
            "fecha_entrega": entrega.fecha_entrega.isoformat() if (entrega and entrega.fecha_entrega) else None,
            "comentario": entrega.comentario if entrega else None,
            "archivo_id": entrega.archivo_id if entrega else None,
            "archivo_nombre": archivo.nombre_archivo if archivo else None,
            "entrega_id": entrega.id if entrega else None,
            "calificado": entrega.calificado if entrega else False,
            "nota": calif.nota if calif else None,
            "feedback": calif.feedback if calif else None,
        })
        
    return result

@router.post("/tareas/{tarea_id}/alumnos/{alumno_id}/entrega")
def get_or_create_student_entrega(tarea_id: int, alumno_id: int, db: Session = Depends(get_db)):
    entrega = db.query(Entrega).filter(Entrega.tarea_id == tarea_id, Entrega.alumno_id == alumno_id).first()
    if not entrega:
        entrega = Entrega(
            tarea_id=tarea_id,
            alumno_id=alumno_id,
            comentario=None,
            archivo_id=None,
            calificado=False
        )
        db.add(entrega)
        db.commit()
        db.refresh(entrega)
    return {
        "id": entrega.id,
        "tarea_id": entrega.tarea_id,
        "alumno_id": entrega.alumno_id,
        "archivo_id": entrega.archivo_id,
        "archivo_nombre": entrega.archivo.nombre_archivo if entrega.archivo else None,
        "comentario": entrega.comentario,
        "calificado": entrega.calificado,
        "nota": entrega.calificacion.nota if entrega.calificacion else None,
        "feedback": entrega.calificacion.feedback if entrega.calificacion else None,
    }

@router.get("/materiales")
def list_materiales(materia_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(MaterialEstudio)
    if materia_id: query = query.filter(MaterialEstudio.materia_id == materia_id)
    return query.all()

from fastapi import UploadFile, File, Form, HTTPException
from app.core.config import get_files_path, get_max_file_size, get_allowed_types
from app.modules.academico.archivos.models import Archivo
import os, uuid
from .models import EntregaComentario, Comunicado, ComunicadoComentario

@router.post("/materiales/subir")
async def subir_material(
    materia_id: int = Form(...),
    titulo: str = Form(...),
    descripcion: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_db)
):
    archivo_id = None
    if file and file.filename:
        content_type = file.content_type
        if not content_type or content_type == "application/octet-stream":
            import mimetypes
            guess, _ = mimetypes.guess_type(file.filename)
            if guess:
                content_type = guess
            else:
                content_type = "application/octet-stream"
        content = await file.read()
        max_size = max(get_max_file_size(), 100 * 1024 * 1024)
        if len(content) > max_size:
            raise HTTPException(status_code=400, detail="Archivo demasiado grande")
        ext = os.path.splitext(file.filename)[1]
        unique_name = f"{uuid.uuid4()}{ext}"
        file_path = os.path.join(get_files_path(), unique_name)
        with open(file_path, "wb") as f: f.write(content)
        archivo = Archivo(alumno_id=None, materia_id=materia_id, nombre_archivo=file.filename, ruta_archivo=file_path, tipo=content_type)
        db.add(archivo); db.flush()
        archivo_id = archivo.id

    material = MaterialEstudio(
        materia_id=materia_id,
        profesor_id=current_user.id,
        titulo=titulo,
        descripcion=descripcion,
        archivo_id=archivo_id
    )
    db.add(material); db.commit(); db.refresh(material)
    return material

@router.post("/tareas/{tarea_id}/entregar")
async def entregar_tarea(
    tarea_id: int,
    comentario: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_db)
):
    from app.modules.academico.alumnos.models import Alumno
    alumno = db.query(Alumno).filter(Alumno.user_id == current_user.id).first()
    alumno_id = alumno.id if alumno else 1

    archivo_id = None
    if file and file.filename:
        content_type = file.content_type
        if not content_type or content_type == "application/octet-stream":
            import mimetypes
            guess, _ = mimetypes.guess_type(file.filename)
            if guess:
                content_type = guess
            else:
                content_type = "application/octet-stream"
        content = await file.read()
        max_size = max(get_max_file_size(), 100 * 1024 * 1024)
        if len(content) > max_size:
            raise HTTPException(status_code=400, detail="Archivo demasiado grande")
        ext = os.path.splitext(file.filename)[1]
        unique_name = f"{uuid.uuid4()}{ext}"
        file_path = os.path.join(get_files_path(), unique_name)
        with open(file_path, "wb") as f: f.write(content)
        archivo = Archivo(alumno_id=alumno_id, materia_id=None, nombre_archivo=file.filename, ruta_archivo=file_path, tipo=content_type)
        db.add(archivo); db.flush()
        archivo_id = archivo.id

    entrega = db.query(Entrega).filter(Entrega.tarea_id == tarea_id, Entrega.alumno_id == alumno_id).first()
    if entrega:
        if archivo_id: entrega.archivo_id = archivo_id
        if comentario is not None: entrega.comentario = comentario
        entrega.fecha_entrega = datetime.utcnow()
    else:
        entrega = Entrega(
            tarea_id=tarea_id,
            alumno_id=alumno_id,
            comentario=comentario,
            archivo_id=archivo_id,
            fecha_entrega=datetime.utcnow()
        )
        db.add(entrega)
    db.commit(); db.refresh(entrega)

    # Notify teacher about the submission
    try:
        from app.modules.notifications.models import Notification
        tarea = db.query(Tarea).filter(Tarea.id == tarea_id).first()
        if tarea and tarea.profesor_id:
            notif = Notification(
                user_id=tarea.profesor_id,
                title=f"Entrega de tarea en {tarea.materia.nombre if tarea.materia else ''}",
                message=f"El alumno {alumno.nombre if alumno else ''} {alumno.apellido if alumno else ''} entregó la tarea: {tarea.titulo}",
                type="tarea"
            )
            db.add(notif)
            db.commit()
    except Exception as e:
        print(f"Error notifying teacher: {e}")

    return entrega

@router.get("/mis-entregas")
def get_mis_entregas(db: Session = Depends(get_db), current_user = Depends(get_current_user_db)):
    from app.modules.academico.alumnos.models import Alumno
    alumno = db.query(Alumno).filter(Alumno.user_id == current_user.id).first()
    if not alumno:
        return []
    entregas = db.query(Entrega).filter(Entrega.alumno_id == alumno.id).all()
    result = []
    for e in entregas:
        calif = e.calificacion
        result.append({
            "id": e.id,
            "tarea_id": e.tarea_id,
            "tarea_title": e.tarea.titulo if e.tarea else "Sin título",
            "materia_nombre": e.tarea.materia.nombre if (e.tarea and e.tarea.materia) else "Sin materia",
            "fecha_entrega": e.fecha_entrega.isoformat() if e.fecha_entrega else None,
            "calificado": e.calificado,
            "nota": calif.nota if (e.calificado and calif) else None,
            "feedback": calif.feedback if (e.calificado and calif) else None,
            "archivo_id": e.archivo_id
        })
    return result

@router.get("/tareas/{tarea_id}/entregas")
def get_entregas_by_tarea_alias(tarea_id: int, db: Session = Depends(get_db)):
    return get_entregas_by_tarea(tarea_id, db)

class CalificacionCreate(BaseModel):
    nota: float
    feedback: Optional[str] = None

@router.post("/entregas/{entrega_id}/calificar")
def calificar_entrega(
    entrega_id: int,
    data: CalificacionCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_db)
):
    entrega = db.query(Entrega).filter(Entrega.id == entrega_id).first()
    if not entrega:
        raise HTTPException(status_code=404, detail="Entrega no encontrada")
    
    calif = db.query(Calificacion).filter(Calificacion.entrega_id == entrega_id).first()
    if calif:
        calif.nota = data.nota
        calif.feedback = data.feedback
        calif.fecha_calificacion = datetime.utcnow()
        calif.profesor_id = current_user.id
    else:
        calif = Calificacion(
            entrega_id=entrega_id,
            profesor_id=current_user.id,
            nota=data.nota,
            feedback=data.feedback,
            fecha_calificacion=datetime.utcnow()
        )
        db.add(calif)
    
    entrega.calificado = True
    db.commit()
    return {"message": "Calificado correctamente"}

@router.get("/comunicados")
def list_comunicados(materia_id: Optional[int] = None, db: Session = Depends(get_db)):
    import json
    query = db.query(Comunicado)
    if materia_id:
        query = query.filter(Comunicado.materia_id == materia_id)
    comunicados = query.order_by(Comunicado.es_fijado.desc(), Comunicado.created_at.desc()).all()
    
    result = []
    for c in comunicados:
        opciones_parsed = None
        if c.opciones:
            try:
                opciones_parsed = json.loads(c.opciones)
            except Exception:
                opciones_parsed = None

        result.append({
            "id": c.id,
            "materia_id": c.materia_id,
            "autor_id": c.autor_id,
            "autor_nombre": c.autor.name if c.autor else "Sistema",
            "mensaje": c.mensaje,
            "tipo": c.tipo or "anuncio",
            "opciones": opciones_parsed,
            "archivo_id": c.archivo_id,
            "archivo_nombre": c.archivo.nombre_archivo if c.archivo else None,
            "es_fijado": bool(c.es_fijado),
            "created_at": c.created_at.isoformat(),
            "comentarios_count": len(c.comentarios)
        })
    return result

class ComunicadoCreate(BaseModel):
    mensaje: str
    materia_id: Optional[int] = None
    tipo: Optional[str] = "anuncio" # 'anuncio', 'encuesta', 'urgente'
    opciones: Optional[list] = None # list of option string titles
    archivo_id: Optional[int] = None
    es_fijado: Optional[bool] = False

@router.post("/comunicados")
def create_comunicado(
    data: ComunicadoCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_db)
):
    import json
    opciones_json = None
    if data.opciones and isinstance(data.opciones, list):
        opciones_list = [{"id": i, "text": str(opt).strip(), "votes": []} for i, opt in enumerate(data.opciones) if str(opt).strip()]
        opciones_json = json.dumps(opciones_list)

    comunicado = Comunicado(
        materia_id=data.materia_id,
        autor_id=current_user.id,
        mensaje=data.mensaje,
        tipo=data.tipo or "anuncio",
        opciones=opciones_json,
        archivo_id=data.archivo_id,
        es_fijado=bool(data.es_fijado)
    )
    db.add(comunicado); db.commit(); db.refresh(comunicado)
    return comunicado

class VotarEncuesta(BaseModel):
    opcion_id: int

@router.post("/comunicados/{comunicado_id}/votar")
def vote_comunicado_poll(
    comunicado_id: int,
    data: VotarEncuesta,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_db)
):
    import json
    comunicado = db.query(Comunicado).filter(Comunicado.id == comunicado_id).first()
    if not comunicado:
        raise HTTPException(status_code=404, detail="Comunicado no encontrado")
    if comunicado.tipo != "encuesta" or not comunicado.opciones:
        raise HTTPException(status_code=400, detail="Este comunicado no es una encuesta válida")

    try:
        opts = json.loads(comunicado.opciones)
    except Exception:
        raise HTTPException(status_code=500, detail="Error al leer opciones de encuesta")

    user_id = current_user.id
    # Remove user vote if already voted on any option
    for opt in opts:
        if "votes" in opt and isinstance(opt["votes"], list):
            if user_id in opt["votes"]:
                opt["votes"].remove(user_id)

    # Vote for target option
    if 0 <= data.opcion_id < len(opts):
        if "votes" not in opts[data.opcion_id] or not isinstance(opts[data.opcion_id]["votes"], list):
            opts[data.opcion_id]["votes"] = []
        opts[data.opcion_id]["votes"].append(user_id)

    comunicado.opciones = json.dumps(opts)
    db.commit()
    return {"message": "Voto registrado correctamente", "opciones": opts}

@router.get("/comunicados/{comunicado_id}/comentarios")
def get_comunicado_comentarios(comunicado_id: int, db: Session = Depends(get_db)):
    comentarios = db.query(ComunicadoComentario).filter(ComunicadoComentario.comunicado_id == comunicado_id).order_by(ComunicadoComentario.created_at.asc()).all()
    return [{
        "id": c.id,
        "autor_nombre": c.autor.name if c.autor else "Anónimo",
        "mensaje": c.mensaje,
        "created_at": c.created_at.isoformat()
    } for c in comentarios]

class ComentarioCreate(BaseModel):
    mensaje: str

@router.post("/comunicados/{comunicado_id}/comentarios")
def add_comunicado_comentario(
    comunicado_id: int,
    data: ComentarioCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_db)
):
    comentario = ComunicadoComentario(
        comunicado_id=comunicado_id,
        autor_id=current_user.id,
        mensaje=data.mensaje
    )
    db.add(comentario); db.commit(); db.refresh(comentario)
    return comentario

@router.get("/entregas/{entrega_id}/comentarios")
def get_entrega_comentarios(entrega_id: int, db: Session = Depends(get_db)):
    comentarios = db.query(EntregaComentario).filter(EntregaComentario.entrega_id == entrega_id).order_by(EntregaComentario.created_at.asc()).all()
    return [{
        "id": c.id,
        "autor_nombre": c.autor.name if c.autor else "Anónimo",
        "autor_id": c.autor_id,
        "mensaje": c.mensaje,
        "created_at": c.created_at.isoformat()
    } for c in comentarios]

@router.post("/entregas/{entrega_id}/comentarios")
def add_entrega_comentario(
    entrega_id: int,
    data: ComentarioCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_db)
):
    comentario = EntregaComentario(
        entrega_id=entrega_id,
        autor_id=current_user.id,
        mensaje=data.mensaje
    )
    db.add(comentario); db.commit(); db.refresh(comentario)
    return comentario


