from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, Date, DateTime, Text
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime

class BoletinPublicado(Base):
    __tablename__ = "boletines_publicados"
    id = Column(Integer, primary_key=True, index=True)
    alumno_id = Column(Integer, ForeignKey("alumnos.id"), nullable=False)
    curso = Column(String, nullable=False) # e.g. "3° 1°"
    anio_lectivo = Column(String, nullable=False) # e.g. "2026"
    periodo = Column(String, nullable=False) # "1° Trimestre", "2° Trimestre", "3° Trimestre", "Anual / Final"
    estado = Column(String, default="borrador") # "borrador", "publicado"
    fecha_creacion = Column(DateTime, default=datetime.utcnow)
    fecha_publicacion = Column(DateTime, nullable=True)
    publicado_por_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    observaciones = Column(Text, nullable=True) # Observaciones / conducta del preceptor
    contenido_json = Column(Text, nullable=False) # JSON con materias, notas, inasistencias y promedios

    alumno = relationship("Alumno", foreign_keys=[alumno_id], backref="boletines_publicados")
    publicado_por = relationship("User", foreign_keys=[publicado_por_id])
