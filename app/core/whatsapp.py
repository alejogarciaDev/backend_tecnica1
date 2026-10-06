import requests
import datetime
import logging
from typing import Optional, Dict, List
from sqlalchemy.orm import Session
from app.modules.whatsapp.models import WhatsappLog
from app.core.database import SessionLocal

logger = logging.getLogger("whatsapp_bot")

# Credenciales de Meta Cloud API
ACCESS_TOKEN = "EAAk1ZCN3kgDwBSulHpdD9xrxqlu3EdTxKpHZCLhOmcZAwGYkHkYiN6OECp2YcdPmLYbWskWejgEmxa1wNyRu39ItYXaBTBKXGeqr30gZA6U4t44woJ6BLzo90CLGsHjwTGVQeHykz1dJ2SjOkQfEWOBCuYW6umxiSGFk8hrfgpq5bPO2URqZAcZAmcKKQPGb1ZCxgZDZD"
PHONE_NUMBER_ID = "1334775246379175"
GLOBAL_BOT_NUMBER = "+54 9 11 3159-2779"

def normalizar_telefono_ar(telefono: str) -> str:
    """
    Limpia y normaliza un número de teléfono argentino al formato E.164 requerido por Meta:
    549 + código de área (sin 0) + número local (sin 15).
    """
    if not telefono:
        return ""
    digits = "".join(filter(str.isdigit, str(telefono)))
    if not digits:
        return ""

    # Quitar cero inicial de área local si existe (ej: 011 -> 11)
    if digits.startswith("0"):
        digits = digits[1:]

    # Si ya tiene el formato completo de Meta 549...
    if digits.startswith("549"):
        return digits

    # Si tiene prefijo de país 54 pero le falta el 9 de móvil (ej: 5411...)
    if digits.startswith("54") and len(digits) >= 11:
        return "549" + digits[2:]

    # Si tiene '15' luego de código de área Buenos Aires (11 15 xxxx xxxx)
    if digits.startswith("1115") and len(digits) == 12:
        digits = "11" + digits[4:]

    # Si es un número local (ej: 1167526216 o 221xxxxxxx)
    if not digits.startswith("54"):
        digits = "549" + digits

    return digits

def enviar_mensaje_whatsapp(
    db: Session,
    destinatario_nombre: str,
    telefono: str,
    mensaje: str,
    tipo: str = "masivo",
    school_id: Optional[int] = None
) -> bool:
    """
    Envía un mensaje de WhatsApp a través de la API en la nube de Meta.
    Registra el log con el school_id correspondiente para aislamiento por colegio.
    """
    num_limpio = normalizar_telefono_ar(telefono)
    if not num_limpio or len(num_limpio) < 10:
        logger.warning(f"Teléfono inválido para {destinatario_nombre}: '{telefono}'")
        return False

    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    # Intentar enviar texto libre
    data = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": num_limpio,
        "type": "text",
        "text": {
            "body": mensaje
        }
    }

    estado = "Fallido"
    try:
        response = requests.post(url, json=data, headers=headers, timeout=8)
        res_json = response.json()
        logger.info(f"Meta API Response ({response.status_code}): {res_json}")

        if response.status_code == 200:
            estado = "Enviado"
        else:
            # Si la ventana de 24 horas no está abierta o requiere template
            logger.info("Envío de texto libre falló. Intentando con plantilla hello_world...")
            data_template = {
                "messaging_product": "whatsapp",
                "to": num_limpio,
                "type": "template",
                "template": {
                    "name": "hello_world",
                    "language": {
                        "code": "en_US"
                    }
                }
            }
            res_temp = requests.post(url, json=data_template, headers=headers, timeout=8)
            if res_temp.status_code == 200:
                estado = "Enviado (Plantilla)"
                logger.info("Plantilla de WhatsApp enviada con éxito.")
            else:
                logger.error(f"Error al enviar plantilla WhatsApp: {res_temp.text}")
    except Exception as e:
        logger.error(f"Error al conectar con la API de Meta: {e}")

    try:
        log = WhatsappLog(
            school_id=school_id,
            remitente=GLOBAL_BOT_NUMBER,
            destinatario=destinatario_nombre,
            telefono=num_limpio,
            mensaje=mensaje if estado == "Enviado" else f"[Plantilla hello_world] {mensaje}",
            tipo=tipo,
            estado=estado,
            fecha_envio=datetime.datetime.utcnow()
        )
        db.add(log)
        db.commit()
        return estado.startswith("Enviado")
    except Exception as e:
        logger.error(f"Error registrando log de Whatsapp: {e}")
        db.rollback()
        return False

def alumno_pertenece_a_curso(alumno, curso_filtro: str) -> bool:
    """
    Determina si un alumno pertenece a un curso dado, evaluando:
    - Campo curso directo ("1ro", "5°", "1er año A")
    - Combinación curso + división ("1ro 1ra", "5° 2da")
    - Registros en alumno_historial
    """
    if not curso_filtro:
        return False
    cf = curso_filtro.strip().lower()

    if alumno.curso and alumno.curso.strip().lower() == cf:
        return True

    curso_div = f"{alumno.curso or ''} {alumno.division or ''}".strip().lower()
    if curso_div and (curso_div == cf or cf in curso_div or curso_div in cf):
        return True

    if hasattr(alumno, "historial") and alumno.historial:
        for h in alumno.historial:
            if h.curso and (h.curso.strip().lower() == cf or cf in h.curso.strip().lower()):
                return True

    return False

def enviar_comunicado_colegio(
    school_id: Optional[int],
    school_name: str,
    target: str,
    title: str,
    message: str,
    tipo: str = "comunicado",
    curso: Optional[str] = None
) -> dict:
    """
    Envía un comunicado institucional por WhatsApp de forma aislada para un colegio específico.
    Se ejecuta típicamente en segundo plano (BackgroundTasks).
    """
    import app.core.models
    from app.modules.schools.models import School
    from app.modules.academico.alumnos.models import Alumno, FamiliarTutor
    from app.modules.profesores.models import Profesor
    from app.modules.users.users.models import User

    db = SessionLocal()
    try:
        header_tipo = {
            "comunicado": "COMUNICADO INSTITUCIONAL",
            "info": "INFORMATIVO GENERAL",
            "alerta": "ALERTA ESCOLAR",
            "urgente": "URGENTE",
        }.get(tipo.lower(), "COMUNICADO")

        nombre_escuela = (school_name or "Comunidad Educativa").strip().upper()
        cuerpo_whatsapp = (
            f"🏫 *{nombre_escuela}*\n"
            f"📢 *{header_tipo}: {title.strip()}*\n\n"
            f"{message.strip()}\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📍 _Mensaje emitido por {nombre_escuela} a través del Bot Institucional._"
        )

        recipients: Dict[str, dict] = {}

        debe_incluir_alumnos = target in (
            "all", "alumnos_tutores", "solo_alumnos", "alumno",
            "curso_alumnos_tutores", "curso_solo_alumnos"
        )
        debe_incluir_tutores = target in (
            "all", "alumnos_tutores", "solo_tutores",
            "curso_alumnos_tutores", "curso_solo_tutores"
        )

        es_filtro_curso = target in (
            "curso_alumnos_tutores", "curso_solo_tutores", "curso_solo_alumnos"
        )

        if debe_incluir_alumnos or debe_incluir_tutores:
            query_alumnos = db.query(Alumno)
            if school_id:
                query_alumnos = query_alumnos.filter(Alumno.school_id == school_id)
            query_alumnos = query_alumnos.filter(Alumno.estado == "Activo")
            alumnos = query_alumnos.all()

            for a in alumnos:
                if es_filtro_curso and curso:
                    if not alumno_pertenece_a_curso(a, curso):
                        continue

                if debe_incluir_alumnos and a.telefono:
                    norm = normalizar_telefono_ar(a.telefono)
                    if norm and norm not in recipients:
                        recipients[norm] = {
                            "nombre": f"Alumno: {a.nombre} {a.apellido}".strip(),
                            "rol": "Alumno"
                        }

                if debe_incluir_tutores and a.familiares:
                    for f in a.familiares:
                        if f.telefono:
                            norm_f = normalizar_telefono_ar(f.telefono)
                            if norm_f and norm_f not in recipients:
                                rel = f.relacion or "Tutor"
                                recipients[norm_f] = {
                                    "nombre": f"{rel}: {f.nombre} {f.apellido} (Tutor de {a.nombre})".strip(),
                                    "rol": "Tutor"
                                }

        debe_incluir_profesores = target in ("all", "personal", "profesor")
        debe_incluir_personal = target in ("all", "personal", "preceptor", "secretaria", "admin")

        if debe_incluir_profesores:
            query_prof = db.query(Profesor)
            if school_id:
                query_prof = query_prof.filter(Profesor.school_id == school_id)
            profesores = query_prof.all()
            for p in profesores:
                if p.telefono:
                    norm_p = normalizar_telefono_ar(p.telefono)
                    if norm_p and norm_p not in recipients:
                        recipients[norm_p] = {
                            "nombre": f"Prof. {p.nombre} {p.apellido}".strip(),
                            "rol": "Profesor"
                        }

        if debe_incluir_personal:
            query_users = db.query(User)
            if school_id:
                query_users = query_users.filter(User.school_id == school_id)
            users = query_users.all()
            for u in users:
                user_phone = getattr(u, "telefono", None)
                if user_phone:
                    norm_u = normalizar_telefono_ar(user_phone)
                    if norm_u and norm_u not in recipients:
                        recipients[norm_u] = {
                            "nombre": u.name,
                            "rol": u.role.name if u.role else "Personal"
                        }

        logger.info(f"Colegio {school_id} ({school_name}) - Destinatarios WhatsApp encontrados: {len(recipients)} para target={target}, curso={curso}")

        enviados = 0
        fallidos = 0
        for tel, info in recipients.items():
            ok = enviar_mensaje_whatsapp(
                db=db,
                destinatario_nombre=info["nombre"],
                telefono=tel,
                mensaje=cuerpo_whatsapp,
                tipo=f"{target}:{curso}" if curso else target,
                school_id=school_id
            )
            if ok:
                enviados += 1
            else:
                fallidos += 1

        return {
            "status": "ok",
            "total_destinatarios": len(recipients),
            "enviados": enviados,
            "fallidos": fallidos
        }
    except Exception as e:
        logger.error(f"Error en enviar_comunicado_colegio: {e}")
        return {
            "status": "error",
            "error": str(e)
        }
    finally:
        db.close()
