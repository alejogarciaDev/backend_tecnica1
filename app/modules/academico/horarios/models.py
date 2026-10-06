from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class Horario(Base):
    __tablename__ = "horarios"
    id = Column(Integer, primary_key=True, index=True)
    materia_id = Column(Integer, ForeignKey("materias.id"), nullable=False)
    dia_semana = Column(String, nullable=False) # Lunes, Martes, Miercoles, Jueves, Viernes, Sabado
    hora_inicio = Column(String, nullable=False) # e.g. "07:30"
    hora_fin = Column(String, nullable=False) # e.g. "09:30"
    aula = Column(String, nullable=True) # e.g. "Aula 5", "Taller Mecanica"

    materia = relationship("Materia", foreign_keys=[materia_id], backref="horarios")
