from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from app.core.database import Base

class Alumno(Base):
    __tablename__ = "alumnos"
    id = Column(Integer, primary_key=True, index=True)
    dni = Column(String, unique=True, index=True)
    nombre = Column(String)
    apellido = Column(String)
    folio = Column(String, nullable=True)
    legajo = Column(String, nullable=True)
    grupo_taller = Column(String, nullable=True) # e.g. "Grupo 1", "Grupo 2", "A", "B"
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True)
    estado = Column(String, default="Activo") # Activo, Traspasado, Egresado, Inactivo (Legacy)
    telefono = Column(String, nullable=True)
    fecha_nacimiento = Column(String, nullable=True)
    curso = Column(String, nullable=True) # e.g. "5°"
    division = Column(String, nullable=True) # e.g. "2°"
    turno = Column(String, nullable=True) # Mañana, Tarde, Vespertino, Doble
    estado_academico = Column(String, default="REGULAR") # REGULAR, INACTIVO, EGRESADO, DADO_DE_BAJA
    estado_cuenta = Column(String, default="SIN_ACTIVAR") # SIN_ACTIVAR, ACTIVACION_PENDIENTE, ACTIVA, BLOQUEADA
    estado_identidad = Column(String, default="NO_VERIFICADA") # NO_VERIFICADA, EN_VERIFICACION, VERIFICADA, RECHAZADA
    
    user = relationship("User", backref="alumno_profile")
    school = relationship("School", backref="alumnos")
    historial = relationship("AlumnoHistorial", back_populates="alumno", cascade="all, delete-orphan", order_by="AlumnoHistorial.anio")
    familiares = relationship("FamiliarTutor", back_populates="alumno", cascade="all, delete-orphan")

class AlumnoHistorial(Base):
    __tablename__ = "alumno_historial"
    id = Column(Integer, primary_key=True, index=True)
    alumno_id = Column(Integer, ForeignKey("alumnos.id"), nullable=False)
    anio = Column(String, nullable=False)
    curso = Column(String, nullable=False)
    repitio = Column(Boolean, default=False)
    observaciones = Column(Text, nullable=True)
    alumno = relationship("Alumno", back_populates="historial")

class FamiliarTutor(Base):
    __tablename__ = "familiares_tutores"
    id = Column(Integer, primary_key=True, index=True)
    alumno_id = Column(Integer, ForeignKey("alumnos.id"), nullable=False)
    nombre = Column(String, nullable=False)
    apellido = Column(String, nullable=False)
    telefono = Column(String, nullable=False)
    relacion = Column(String, nullable=False) # Madre, Padre, Tutor, Familiar, etc.
    
    alumno = relationship("Alumno", back_populates="familiares")
