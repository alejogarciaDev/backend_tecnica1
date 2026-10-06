from sqlalchemy import Column, Integer, String, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.core.database import Base

class Tramite(Base):
    __tablename__ = "tramites"
    id = Column(Integer, primary_key=True, index=True)
    alumno_id = Column(Integer, ForeignKey("alumnos.id"), nullable=False)
    tipo_tramite = Column(String, nullable=False)  # e.g., "Constancia de Alumno Regular", "Certificado Analitico"
    fecha_solicitud = Column(String, nullable=False)
    estado = Column(String, default="Pendiente")  # "Pendiente", "En Proceso", "Listo"
    observaciones = Column(Text, nullable=True)

    alumno = relationship("Alumno")
