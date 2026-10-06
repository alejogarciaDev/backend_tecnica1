from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime

class Olimpiada(Base):
    __tablename__ = "olimpiadas"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    activa = Column(Boolean, default=True)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)

class CategoriaOlimpiada(Base):
    __tablename__ = "olimpiadas_categorias"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False) # e.g. Nivel 1, Nivel 2

class TipoOlimpiada(Base):
    __tablename__ = "olimpiadas_tipos"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False) # e.g. Matemáticas, Programación

class InscripcionOlimpiada(Base):
    __tablename__ = "olimpiadas_inscripciones"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    olimpiada_id = Column(Integer, ForeignKey("olimpiadas.id"), nullable=False)
    categoria_id = Column(Integer, ForeignKey("olimpiadas_categorias.id"), nullable=False)
    tipo_id = Column(Integer, ForeignKey("olimpiadas_tipos.id"), nullable=False)
    fecha_inscripcion = Column(DateTime, default=datetime.utcnow)
    
    # Relationships for easy access
    user = relationship("User")
    olimpiada = relationship("Olimpiada")
    categoria = relationship("CategoriaOlimpiada")
    tipo = relationship("TipoOlimpiada")
