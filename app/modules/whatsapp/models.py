from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from app.core.database import Base
from datetime import datetime

class WhatsappLog(Base):
    __tablename__ = "whatsapp_logs"
    id = Column(Integer, primary_key=True, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True)
    remitente = Column(String(50), nullable=True)
    destinatario = Column(String(200), nullable=False)
    telefono = Column(String(50), nullable=False)
    mensaje = Column(Text, nullable=False)
    tipo = Column(String(50), default="masivo") # masivo, curso, privado, etc.
    estado = Column(String(50), default="Enviado")
    fecha_envio = Column(DateTime, default=datetime.utcnow)
