from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base

class Curso(Base):
    __tablename__ = "cursos"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, index=True, nullable=False)
    turno = Column(String, nullable=False) # Mañana, Tarde, Vespertino
    anio = Column(String, nullable=True) # e.g. "1ro", "2do", ..., "7mo"
    division = Column(String, nullable=True) # e.g. "1ra", "2da", "3ra", "A", "B"
    preceptor_principal_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True)

    preceptor_principal = relationship("User", foreign_keys=[preceptor_principal_id])
    school = relationship("School", backref="cursos")

    __table_args__ = (
        UniqueConstraint('school_id', 'nombre', name='_school_curso_uc'),
    )
