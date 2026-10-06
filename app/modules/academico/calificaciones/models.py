from sqlalchemy import Column, Integer, String, ForeignKey, Float, Boolean, Date, DateTime, Text
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import date, datetime

class CalificacionAcademica(Base):
    __tablename__ = "calificaciones_academicas"
    id = Column(Integer, primary_key=True, index=True)
    alumno_id = Column(Integer, ForeignKey("alumnos.id"), nullable=False)
    materia_id = Column(Integer, ForeignKey("materias.id"), nullable=False)
    periodo = Column(String, nullable=False) # "1° Trimestre", "2° Trimestre", "3° Trimestre", "Final"
    nota = Column(Float, nullable=False)
    fecha = Column(Date, default=date.today)
    profesor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    aprobado_preceptor = Column(Boolean, default=False)
    aprobado_por_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    alumno = relationship("Alumno", foreign_keys=[alumno_id], backref="calificaciones_academicas")
    materia = relationship("Materia", foreign_keys=[materia_id], backref="calificaciones_academicas")
    profesor = relationship("User", foreign_keys=[profesor_id])
    aprobado_por = relationship("User", foreign_keys=[aprobado_por_id])


class Evaluacion(Base):
    """Evaluación parcial, examen, prueba o trabajo evaluado por el profesor con fecha acumulativa."""
    __tablename__ = "evaluaciones"
    id = Column(Integer, primary_key=True, index=True)
    materia_id = Column(Integer, ForeignKey("materias.id"), nullable=False)
    profesor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    titulo = Column(String, nullable=False) # e.g. "Prueba de Circuitos 1", "TP Evaluativo"
    tipo = Column(String, default="Prueba") # "Prueba", "Examen", "Trabajo Práctico", "Oral", "Concepto"
    fecha = Column(Date, default=date.today)
    periodo = Column(String, default="1° Trimestre") # "1° Trimestre", "2° Trimestre", "3° Trimestre"
    descripcion = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    materia = relationship("Materia", foreign_keys=[materia_id], backref="evaluaciones")
    profesor = relationship("User", foreign_keys=[profesor_id])
    notas = relationship("EvaluacionNota", back_populates="evaluacion", cascade="all, delete-orphan")


class EvaluacionNota(Base):
    """Calificación individual de un alumno en una evaluación específica."""
    __tablename__ = "evaluaciones_notas"
    id = Column(Integer, primary_key=True, index=True)
    evaluacion_id = Column(Integer, ForeignKey("evaluaciones.id"), nullable=False)
    alumno_id = Column(Integer, ForeignKey("alumnos.id"), nullable=False)
    nota = Column(Float, nullable=False) # 1 a 10 o 0 a 100
    observacion = Column(String, nullable=True)

    evaluacion = relationship("Evaluacion", back_populates="notas")
    alumno = relationship("Alumno", foreign_keys=[alumno_id], backref="evaluaciones_notas")
