from sqlalchemy import Column, Integer, String, ForeignKey, Date
from sqlalchemy.orm import relationship
from app.core.database import Base

class Asistencia(Base):
    __tablename__ = "asistencias"
    id = Column(Integer, primary_key=True, index=True)
    alumno_id = Column(Integer, ForeignKey("alumnos.id"), nullable=False)
    fecha = Column(Date, nullable=False)
    turno = Column(String, nullable=False) # Mañana, Tarde, Taller
    estado = Column(String, nullable=False) # Presente, Ausente, Tarde
    registrado_por_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    alumno = relationship("Alumno", foreign_keys=[alumno_id])
    registrado_por = relationship("User", foreign_keys=[registrado_por_id])
