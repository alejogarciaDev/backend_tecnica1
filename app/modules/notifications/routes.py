from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from app.core.database import get_db
from app.core.security import get_current_user_db
from app.modules.users.users.models import User
from app.modules.users.roles.models import Role
from app.modules.schools.models import School
from app.modules.academico.alumnos.models import Alumno
from app.core.whatsapp import enviar_comunicado_colegio, alumno_pertenece_a_curso
from .models import Notification

router = APIRouter(prefix="/notifications", tags=["Notificaciones"])

class BroadcastNotificationRequest(BaseModel):
    title: str
    message: str
    type: str = "info" # info, alerta, urgente, comunicado
    target: str = "all" # all, personal, profesor, alumnos_tutores, solo_tutores, solo_alumnos, curso_alumnos_tutores, curso_solo_tutores, curso_solo_alumnos, preceptor, secretaria, alumno
    curso: Optional[str] = None
    send_whatsapp: bool = True

def format_notification(n: Notification):
    return {
        "id": n.id,
        "user_id": n.user_id,
        "title": n.title,
        "message": n.message,
        "type": n.type,
        "read": bool(n.read),
        "is_read": bool(n.read),
        "created_at": n.created_at.strftime("%Y-%m-%d %H:%M:%S") if n.created_at else None
    }

@router.get("/")
@router.get("")
def list_notifications(db: Session = Depends(get_db), user=Depends(get_current_user_db)):
    notifs = db.query(Notification).filter(Notification.user_id == user.id).order_by(Notification.created_at.desc()).all()
    return [format_notification(n) for n in notifs]

@router.get("/count")
def count_unread(db: Session = Depends(get_db), user=Depends(get_current_user_db)):
    count = db.query(Notification).filter(Notification.user_id == user.id, Notification.read == False).count()
    return {"unread": count}

@router.post("/{notif_id}/read")
def mark_read(notif_id: int, db: Session = Depends(get_db)):
    notif = db.query(Notification).filter(Notification.id == notif_id).first()
    if notif:
        notif.read = True
        db.commit()
    return {"status": "ok"}

@router.post("/broadcast")
def broadcast_notification(
    data: BroadcastNotificationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_db)
):
    role_name = (user.role.name if user.role else "").lower().strip()
    if role_name not in ("admin", "superadmin", "secretaria", "preceptor"):
        raise HTTPException(status_code=403, detail="No autorizado para emitir comunicados institucionales")

    school_id = user.school_id
    school_name = "Escuela"
    if school_id:
        school = db.query(School).filter(School.id == school_id).first()
        if school:
            school_name = school.name
    elif hasattr(user, "school") and user.school:
        school_name = user.school.name
        school_id = user.school.id

    query = db.query(User)
    if school_id:
        query = query.filter(User.school_id == school_id)

    alumno_role = db.query(Role).filter(Role.name == "alumno").first()
    alumno_role_id = alumno_role.id if alumno_role else -1

    target_users: List[User] = []

    if data.target == "personal":
        target_users = query.filter(User.role_id != alumno_role_id).all()
    elif data.target in ("profesor", "preceptor", "secretaria", "admin"):
        target_role = db.query(Role).filter(Role.name == data.target).first()
        if target_role:
            target_users = query.filter(User.role_id == target_role.id).all()
        else:
            target_users = []
    elif data.target in ("solo_alumnos", "alumno"):
        target_users = query.filter(User.role_id == alumno_role_id).all()
    elif data.target == "solo_tutores":
        tutor_role = db.query(Role).filter(Role.name.in_(["tutor", "padre", "familiar"])).first()
        if tutor_role:
            target_users = query.filter(User.role_id == tutor_role.id).all()
        else:
            target_users = []
    elif data.target in ("curso_alumnos_tutores", "curso_solo_alumnos"):
        potential = query.filter(User.role_id == alumno_role_id).all()
        for u in potential:
            perfil = db.query(Alumno).filter(Alumno.user_id == u.id).first()
            if perfil and data.curso and alumno_pertenece_a_curso(perfil, data.curso):
                target_users.append(u)
    elif data.target == "curso_solo_tutores":
        target_users = []
    else: # "all" o "alumnos_tutores"
        target_users = query.all()

    created_count = 0
    for u in target_users:
        notif = Notification(
            user_id=u.id,
            title=data.title,
            message=data.message,
            type=data.type,
            read=False
        )
        db.add(notif)
        created_count += 1

    db.commit()

    # Si se solicitó WhatsApp, se despacha en segundo plano con aislamiento por colegio
    if data.send_whatsapp:
        background_tasks.add_task(
            enviar_comunicado_colegio,
            school_id=school_id,
            school_name=school_name,
            target=data.target,
            title=data.title,
            message=data.message,
            tipo=data.type,
            curso=data.curso
        )

    msg_status = f"Comunicado enviado a {created_count} usuarios en la app"
    if data.send_whatsapp:
        msg_status += " y encolado para WhatsApp vía Bot Institucional"

    return {
        "status": "ok",
        "message": msg_status,
        "recipients_count": created_count,
        "whatsapp_enabled": data.send_whatsapp
    }

@router.get("/admin-list")
def list_admin_notifications(
    limit: int = 50,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_db)
):
    role_name = (user.role.name if user.role else "").lower().strip()
    if role_name not in ("admin", "superadmin", "secretaria", "preceptor"):
        raise HTTPException(status_code=403, detail="No autorizado")

    query = db.query(Notification)
    if user.school_id and role_name != "superadmin":
        query = query.join(User, Notification.user_id == User.id).filter(User.school_id == user.school_id)

    notifs = query.order_by(Notification.created_at.desc()).limit(limit).all()
    return [format_notification(n) for n in notifs]
