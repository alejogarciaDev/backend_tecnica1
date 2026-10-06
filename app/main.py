from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from app.core.database import Base, engine
from app.core.school_config import get_school_config
import app.core.models

from app.modules.auth.routes import router as auth_router
from app.modules.users.users.routes import router as users_router
from app.modules.users.roles.routes import router as roles_router
from app.modules.users.permissions.routes import router as permissions_router
from app.modules.school.routes import router as school_router
from app.modules.drive.routes import router as drive_router

cfg = get_school_config()

app = FastAPI(title=f"SIGEN - {cfg.name}", description="Sistema de Gestión Educativa Multi-escuela", version="1.0.0-beta", redirect_slashes=False)

cors_origins_env = os.getenv("CORS_ALLOWED_ORIGINS", "")
if cors_origins_env:
    origins = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]
else:
    origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

from app.modules.academico.cursos.routes import router as cursos_router
from app.modules.academico.asistencias.routes import router as asistencias_router
from app.modules.academico.calificaciones.routes import router as calificaciones_router
from app.modules.academico.horarios.routes import router as horarios_router
from app.modules.academico.boletines.routes import router as boletines_router
from app.modules.whatsapp.routes import router as whatsapp_router
from app.modules.notifications.routes import router as notif_router

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(roles_router)
app.include_router(permissions_router)
app.include_router(school_router)
app.include_router(drive_router)
app.include_router(cursos_router)
app.include_router(asistencias_router)
app.include_router(calificaciones_router)
app.include_router(horarios_router)
app.include_router(boletines_router)
app.include_router(whatsapp_router)
app.include_router(notif_router)

from app.modules.secretaria.routes import router as secretaria_router
app.include_router(secretaria_router)

# Olimpiadas - importar DESPUÉS de core.models para que User/Role estén registrados
from app.modules.olimpiadas.router import router as olimpiadas_router
app.include_router(olimpiadas_router)
if cfg.modules.get("panol"):
    from app.modules.panol.categories.routes import router as cat_router
    from app.modules.panol.loans.routes import router as loans_router
    from app.modules.panol.orders.routes import router as orders_router
    app.include_router(cat_router)
    app.include_router(loans_router)
    app.include_router(orders_router)

if cfg.modules.get("alumnos"):
    from app.modules.academico.alumnos.routes import router as alumnos_router
    app.include_router(alumnos_router)

if cfg.modules.get("materias"):
    from app.modules.academico.materias.routes import router as materias_router
    app.include_router(materias_router)

if cfg.modules.get("campus"):
    from app.modules.campus.routes import router as campus_router
    app.include_router(campus_router)


if cfg.modules.get("archivos") or cfg.modules.get("alumnos"):
    from app.modules.academico.archivos.routes import router as archivos_router
    app.include_router(archivos_router)

if cfg.modules.get("profesores"):
    from app.modules.profesores.routes import router as profesores_router
    app.include_router(profesores_router)

if cfg.modules.get("oficina_alumnos"):
    from app.modules.oficina_alumnos.routes import router as oficina_router
    app.include_router(oficina_router)

# Carga dinámica de plugins
from app.core.plugin_loader import plugin_loader
plugin_loader.load_active_plugins(app)

# Crear tablas en la base de datos (Core + Plugins cargados)
Base.metadata.create_all(bind=engine)

@app.on_event("startup")
def startup_db_checks():
    from sqlalchemy import text
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE whatsapp_logs ADD COLUMN IF NOT EXISTS school_id INTEGER;"))
            conn.commit()
        except Exception:
            try:
                conn.execute(text("ALTER TABLE whatsapp_logs ADD COLUMN school_id INTEGER;"))
                conn.commit()
            except Exception:
                pass

@app.get("/health")
def health():
    return {"status": "ok", "school": cfg.name, "version": "1.0.0-beta", "modules": {k: v for k, v in cfg.modules.items() if v}}

