from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from datetime import datetime
from app.core.database import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    user_email = Column(String, nullable=True)
    user_name = Column(String, nullable=True)
    user_role = Column(String, nullable=True)
    action = Column(String, nullable=False, index=True)
    # CREAR_ALUMNO, EDITAR_ALUMNO, CAMBIAR_ESTADO, DAR_DE_BAJA, REACTIVAR_ALUMNO,
    # BLOQUEAR_CUENTA, DESBLOQUEAR_CUENTA, REINICIAR_CONTRASENA_ALUMNO, CAMBIAR_CONTRASENA_ALUMNO
    target_id = Column(Integer, nullable=True)
    target_dni = Column(String, nullable=True, index=True)
    target_name = Column(String, nullable=True)
    details = Column(Text, nullable=True)
    status = Column(String, default="EXITOSO") # EXITOSO, FALLIDO
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
