from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, Date
from sqlalchemy.orm import relationship
from app.core.database import Base

class Libro(Base):
    __tablename__ = "libros"
    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String, nullable=False)
    autor = Column(String, nullable=False)
    isbn = Column(String, unique=True, index=True, nullable=True)
    editorial = Column(String, nullable=True)
    copias_totales = Column(Integer, default=1)
    copias_disponibles = Column(Integer, default=1)

class PrestamoLibro(Base):
    __tablename__ = "prestamos_libros"
    id = Column(Integer, primary_key=True, index=True)
    libro_id = Column(Integer, ForeignKey("libros.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    fecha_prestamo = Column(String, nullable=False)  # ISO string or date
    fecha_devolucion = Column(String, nullable=True)
    devuelto = Column(Boolean, default=False)
    estado = Column(String, default="solicitado")  # "solicitado", "listo_para_retirar", "prestado", "devuelto"

    libro = relationship("Libro")
    user = relationship("User")
