from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Float, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class DocumentoAlumno(Base):
    __tablename__ = "documentos_alumno"
    id = Column(Integer, primary_key=True, index=True)
    alumno_id = Column(Integer, ForeignKey("alumnos.id"), nullable=False)
    nombre = Column(String, nullable=False)
    es_carpeta = Column(Boolean, default=False)
    carpeta_padre_id = Column(Integer, ForeignKey("documentos_alumno.id"), nullable=True)
    archivo_id = Column(Integer, ForeignKey("archivos.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    alumno = relationship("Alumno", backref="documentos")
    archivo = relationship("Archivo", backref="documento_alumno", uselist=False)
    padre = relationship("DocumentoAlumno", backref="subcarpetas", remote_side=[id], cascade="all")

class Tarea(Base):
    __tablename__ = "tareas"
    id = Column(Integer, primary_key=True, index=True)
    materia_id = Column(Integer, ForeignKey("materias.id"), nullable=False)
    profesor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    titulo = Column(String, nullable=False)
    descripcion = Column(Text, nullable=True)
    fecha_limite = Column(DateTime, nullable=True)
    activa = Column(Boolean, default=True)
    archivo_id = Column(Integer, ForeignKey("archivos.id"), nullable=True)
    tipo = Column(String, default="tarea")
    created_at = Column(DateTime, default=datetime.utcnow)
    materia = relationship("Materia", backref="tareas")
    profesor = relationship("User", backref="tareas_creadas")
    archivo = relationship("Archivo", backref="tareas_adjuntas")
    entregas = relationship("Entrega", backref="tarea", cascade="all, delete-orphan")

class Entrega(Base):
    __tablename__ = "entregas"
    id = Column(Integer, primary_key=True, index=True)
    tarea_id = Column(Integer, ForeignKey("tareas.id"), nullable=False)
    alumno_id = Column(Integer, ForeignKey("alumnos.id"), nullable=False)
    archivo_id = Column(Integer, ForeignKey("archivos.id"), nullable=True)
    comentario = Column(Text, nullable=True)
    fecha_entrega = Column(DateTime, default=datetime.utcnow)
    calificado = Column(Boolean, default=False)
    alumno = relationship("Alumno", backref="entregas")
    archivo = relationship("Archivo", backref="entrega", uselist=False)
    calificacion = relationship("Calificacion", backref="entrega", uselist=False, cascade="all, delete-orphan")

class Calificacion(Base):
    __tablename__ = "calificaciones"
    id = Column(Integer, primary_key=True, index=True)
    entrega_id = Column(Integer, ForeignKey("entregas.id"), nullable=False, unique=True)
    profesor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    nota = Column(Float, nullable=False)
    feedback = Column(Text, nullable=True)
    fecha_calificacion = Column(DateTime, default=datetime.utcnow)
    profesor = relationship("User", backref="calificaciones")

class MaterialEstudio(Base):
    __tablename__ = "materiales_estudio"
    id = Column(Integer, primary_key=True, index=True)
    materia_id = Column(Integer, ForeignKey("materias.id"), nullable=False)
    profesor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    titulo = Column(String, nullable=False)
    descripcion = Column(Text, nullable=True)
    archivo_id = Column(Integer, ForeignKey("archivos.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    materia = relationship("Materia", backref="materiales")
    profesor = relationship("User", backref="materiales_subidos")
    archivo = relationship("Archivo", backref="material_estudio")

class DocumentoCompartido(Base):
    __tablename__ = "documentos_compartidos"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    es_carpeta = Column(Boolean, default=False)
    carpeta_padre_id = Column(Integer, ForeignKey("documentos_compartidos.id"), nullable=True)
    archivo_id = Column(Integer, ForeignKey("archivos.id"), nullable=True)
    creador_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    creador = relationship("User", backref="documentos_compartidos")
    archivo = relationship("Archivo", backref="documento_compartido", uselist=False)
    padre = relationship("DocumentoCompartido", backref="subcarpetas_compartidas", remote_side=[id], cascade="all")
    permisos = relationship("CompartidoPermiso", backref="carpeta", cascade="all, delete-orphan")

class CompartidoPermiso(Base):
    __tablename__ = "compartidos_permisos"
    id = Column(Integer, primary_key=True, index=True)
    carpeta_id = Column(Integer, ForeignKey("documentos_compartidos.id", ondelete="CASCADE"), nullable=False)
    tipo = Column(String, nullable=False)
    destino_id = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Comunicado(Base):
    __tablename__ = "comunicados"
    id = Column(Integer, primary_key=True, index=True)
    materia_id = Column(Integer, ForeignKey("materias.id"), nullable=True)
    autor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    mensaje = Column(Text, nullable=False)
    tipo = Column(String, default="anuncio") # 'anuncio', 'encuesta', 'urgente'
    opciones = Column(Text, nullable=True) # JSON array of options e.g. [{"text": "opcion", "votes": [1, 2]}]
    archivo_id = Column(Integer, ForeignKey("archivos.id"), nullable=True)
    es_fijado = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    autor = relationship("User")
    archivo = relationship("Archivo", uselist=False)
    comentarios = relationship("ComunicadoComentario", backref="comunicado", cascade="all, delete-orphan")

class ComunicadoComentario(Base):
    __tablename__ = "comunicados_comentarios"
    id = Column(Integer, primary_key=True, index=True)
    comunicado_id = Column(Integer, ForeignKey("comunicados.id", ondelete="CASCADE"), nullable=False)
    autor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    mensaje = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    autor = relationship("User")

class EntregaComentario(Base):
    __tablename__ = "entregas_comentarios"
    id = Column(Integer, primary_key=True, index=True)
    entrega_id = Column(Integer, ForeignKey("entregas.id", ondelete="CASCADE"), nullable=False)
    autor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    mensaje = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    autor = relationship("User")
    entrega = relationship("Entrega", backref="comentarios_discusion")
