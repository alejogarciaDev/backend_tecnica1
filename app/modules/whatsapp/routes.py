from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.core.database import get_db
from .models import WhatsappLog
from app.modules.academico.alumnos.models import Alumno
from app.modules.academico.alumnos.models import FamiliarTutor
from app.modules.academico.alumnos.models import AlumnoHistorial
from app.core.whatsapp import enviar_mensaje_whatsapp, enviar_comunicado_colegio
from app.core.security import get_current_user_db
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp Bot"])

class GeneralBroadcast(BaseModel):
    mensaje: str

class CourseBroadcast(BaseModel):
    curso: str
    mensaje: str

@router.get("/logs", response_model=List[dict])
def get_whatsapp_logs(db: Session = Depends(get_db), current_user = Depends(get_current_user_db)):
    role_name = (current_user.role.name if current_user.role else "").lower()
    query = db.query(WhatsappLog)
    if role_name != "superadmin" and current_user.school_id:
        query = query.filter(WhatsappLog.school_id == current_user.school_id)
    logs = query.order_by(WhatsappLog.fecha_envio.desc()).limit(100).all()
    res = []
    for l in logs:
        res.append({
            "id": l.id,
            "school_id": l.school_id,
            "remitente": l.remitente or "",
            "destinatario": l.destinatario,
            "telefono": l.telefono,
            "mensaje": l.mensaje,
            "tipo": l.tipo,
            "estado": l.estado,
            "fecha_envio": str(l.fecha_envio)
        })
    return res

@router.post("/comunicado-general")
def enviar_comunicado_general(
    data: GeneralBroadcast,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_db)
):
    school_id = current_user.school_id
    school_name = current_user.school.name if hasattr(current_user, "school") and current_user.school else "Colegio"
    background_tasks.add_task(
        enviar_comunicado_colegio,
        school_id=school_id,
        school_name=school_name,
        target="alumnos_tutores",
        title="Comunicado General",
        message=data.mensaje,
        tipo="comunicado"
    )
    return {"status": "ok", "message": "Comunicado general encolado para WhatsApp."}

@router.post("/comunicado-curso")
def enviar_comunicado_curso(
    data: CourseBroadcast,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_db)
):
    school_id = current_user.school_id
    school_name = current_user.school.name if hasattr(current_user, "school") and current_user.school else "Colegio"
    background_tasks.add_task(
        enviar_comunicado_colegio,
        school_id=school_id,
        school_name=school_name,
        target="curso_alumnos_tutores",
        title=f"Aviso para Curso {data.curso}",
        message=data.mensaje,
        tipo="comunicado",
        curso=data.curso
    )
    return {"status": "ok", "message": f"Comunicado para el curso {data.curso} encolado para WhatsApp."}
