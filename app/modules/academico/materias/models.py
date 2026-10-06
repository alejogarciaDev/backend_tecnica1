from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base

class Materia(Base):
    __tablename__ = "materias"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, index=True)
    descripcion = Column(String, nullable=True)
    profesor_id = Column(Integer, ForeignKey("profesores.id"), nullable=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True)
    curso = Column(String, nullable=True)
    tipo = Column(String, default="aula", nullable=False) # aula or taller
    
    profesor = relationship("Profesor", back_populates="materias")
    school = relationship("School", backref="materias")

    __table_args__ = (
        UniqueConstraint('school_id', 'nombre', name='_school_materia_uc'),
    )

