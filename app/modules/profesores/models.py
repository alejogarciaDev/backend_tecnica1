from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class Profesor(Base):
    __tablename__ = "profesores"
    id = Column(Integer, primary_key=True, index=True)
    dni = Column(String, unique=True, index=True, nullable=False)
    nombre = Column(String, nullable=False)
    apellido = Column(String, nullable=False)
    especialidad = Column(String, nullable=True)
    telefono = Column(String, nullable=True)
    tipo = Column(String, default="aula", nullable=False) # aula or taller
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True)
    
    user = relationship("User", backref="profesor_profile")
    school = relationship("School", backref="profesores")
    materias = relationship("Materia", back_populates="profesor")
