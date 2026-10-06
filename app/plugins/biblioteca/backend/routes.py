from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from .models import Libro, PrestamoLibro
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

router = APIRouter(prefix="/biblioteca", tags=["Biblioteca"])

class LibroCreate(BaseModel):
    titulo: str
    autor: str
    isbn: Optional[str] = None
    editorial: Optional[str] = None
    copias_totales: int = 1

class AgregarCopiasData(BaseModel):
    cantidad: int

class PrestamoCreate(BaseModel):
    libro_id: int
    user_id: Optional[int] = None

@router.get("/libros")
@router.get("/libros/")
def listar_libros(db: Session = Depends(get_db)):
    return db.query(Libro).all()

@router.post("/libros")
@router.post("/libros/")
def crear_libro(data: LibroCreate, db: Session = Depends(get_db)):
    if data.isbn:
        existing = db.query(Libro).filter(Libro.isbn == data.isbn).first()
        if existing:
            raise HTTPException(status_code=400, detail="Ya existe un libro con ese ISBN")
    
    libro = Libro(
        titulo=data.titulo,
        autor=data.autor,
        isbn=data.isbn,
        editorial=data.editorial,
        copias_totales=data.copias_totales,
        copias_disponibles=data.copias_totales
    )
    db.add(libro)
    db.commit()
    db.refresh(libro)
    return libro

def _notificar_usuario(db: Session, user_id: int, title: str, message: str, tipo: str = "biblioteca"):
    try:
        from app.modules.notifications.models import Notification
        notif = Notification(
            user_id=user_id,
            title=title,
            message=message,
            type=tipo,
            read=False
        )
        db.add(notif)
        db.commit()
    except Exception as e:
        print(f"Error registrando notificación de biblioteca: {e}")

@router.get("/prestamos")
@router.get("/prestamos/")
def listar_prestamos(db: Session = Depends(get_db)):
    prestamos = db.query(PrestamoLibro).order_by(PrestamoLibro.id.desc()).all()
    res = []
    for p in prestamos:
        st = getattr(p, "estado", None)
        if not st:
            st = "devuelto" if p.devuelto else "prestado"
        res.append({
            "id": p.id,
            "libro_id": p.libro_id,
            "libro_titulo": p.libro.titulo if p.libro else "Desconocido",
            "libro_autor": p.libro.autor if p.libro else "Desconocido",
            "user_id": p.user_id,
            "user_name": p.user.name if p.user else "Desconocido",
            "fecha_prestamo": p.fecha_prestamo,
            "fecha_devolucion": p.fecha_devolucion,
            "devuelto": p.devuelto,
            "estado": st
        })
    return res

@router.get("/prestamos/mis-prestamos")
@router.get("/prestamos/mis-prestamos/")
def mis_prestamos(request: Request, db: Session = Depends(get_db)):
    """Devuelve los préstamos del usuario autenticado (user_id viene del request state)."""
    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        raise HTTPException(status_code=401, detail="No autenticado")
    prestamos = db.query(PrestamoLibro).filter(PrestamoLibro.user_id == user_id).order_by(PrestamoLibro.id.desc()).all()
    res = []
    for p in prestamos:
        st = getattr(p, "estado", None)
        if not st:
            st = "devuelto" if p.devuelto else "prestado"
        res.append({
            "id": p.id,
            "libro_id": p.libro_id,
            "libro_titulo": p.libro.titulo if p.libro else "Desconocido",
            "libro_autor": p.libro.autor if p.libro else "Desconocido",
            "user_id": p.user_id,
            "fecha_prestamo": p.fecha_prestamo,
            "fecha_devolucion": p.fecha_devolucion,
            "devuelto": p.devuelto,
            "estado": st
        })
    return res

@router.post("/prestamos")
@router.post("/prestamos/")
def crear_prestamo(data: PrestamoCreate, request: Request, db: Session = Depends(get_db)):
    from app.modules.users.users.models import User
    u_id = data.user_id
    valid_user = None
    if u_id:
        valid_user = db.query(User).filter(User.id == u_id).first()
    if not valid_user:
        state_u_id = getattr(request.state, "user_id", None)
        if state_u_id:
            valid_user = db.query(User).filter(User.id == state_u_id).first()
    if not valid_user:
        valid_user = db.query(User).first()
    if not valid_user:
        valid_user = User(name="Usuario Sistema", email="sistema@escuela.edu.ar", password="password", role_id=1)
        db.add(valid_user)
        db.commit()
        db.refresh(valid_user)

    final_user_id = valid_user.id

    libro = db.query(Libro).filter(Libro.id == data.libro_id).first()
    if not libro:
        raise HTTPException(status_code=404, detail="Libro no encontrado")
    if libro.copias_disponibles <= 0:
        raise HTTPException(status_code=400, detail="No hay copias disponibles de este libro")
    
    libro.copias_disponibles -= 1
    
    prestamo = PrestamoLibro(
        libro_id=data.libro_id,
        user_id=final_user_id,
        fecha_prestamo=datetime.now().strftime("%Y-%m-%d"),
        devuelto=False,
        estado="solicitado"
    )
    db.add(prestamo)
    db.commit()
    db.refresh(prestamo)
    
    _notificar_usuario(
        db=db,
        user_id=final_user_id,
        title="📚 Solicitud de libro registrada",
        message=f"Solicitaste '{libro.titulo}'. La bibliotecaria preparará tu libro a la brevedad.",
        tipo="biblioteca"
    )
    return prestamo

@router.post("/prestamos/{prestamo_id}/preparar")
@router.post("/prestamos/{prestamo_id}/preparar/")
@router.post("/prestamos/{prestamo_id}/listo")
@router.post("/prestamos/{prestamo_id}/listo/")
def marcar_libro_listo(prestamo_id: int, db: Session = Depends(get_db)):
    """La bibliotecaria marca el libro como listo para retirar y envía una notificación al alumno/usuario."""
    prestamo = db.query(PrestamoLibro).filter(PrestamoLibro.id == prestamo_id).first()
    if not prestamo:
        raise HTTPException(status_code=404, detail="Préstamo no encontrado")
    
    prestamo.estado = "listo_para_retirar"
    db.commit()
    
    titulo_libro = prestamo.libro.titulo if prestamo.libro else "solicitado"
    _notificar_usuario(
        db=db,
        user_id=prestamo.user_id,
        title="📦 ¡Tu libro está listo para retirar!",
        message=f"Tu libro '{titulo_libro}' ya se encuentra preparado en la Biblioteca. ¡Puedes pasar a buscarlo!",
        tipo="biblioteca"
    )
    return {"status": "ok", "message": "Libro marcado como listo para retirar y notificación enviada", "estado": "listo_para_retirar"}

@router.post("/prestamos/{prestamo_id}/entregar")
@router.post("/prestamos/{prestamo_id}/entregar/")
def marcar_libro_entregado(prestamo_id: int, db: Session = Depends(get_db)):
    """La bibliotecaria entrega físicamente el libro al usuario."""
    prestamo = db.query(PrestamoLibro).filter(PrestamoLibro.id == prestamo_id).first()
    if not prestamo:
        raise HTTPException(status_code=404, detail="Préstamo no encontrado")
    
    prestamo.estado = "prestado"
    prestamo.devuelto = False
    prestamo.fecha_prestamo = datetime.now().strftime("%Y-%m-%d")
    db.commit()
    
    titulo_libro = prestamo.libro.titulo if prestamo.libro else "solicitado"
    _notificar_usuario(
        db=db,
        user_id=prestamo.user_id,
        title="📖 Libro retirado",
        message=f"Retiraste el libro '{titulo_libro}'. Recuerda conservarlo bien y devolverlo en fecha.",
        tipo="biblioteca"
    )
    return {"status": "ok", "message": "Préstamo asentado como retirado con éxito", "estado": "prestado"}

@router.post("/prestamos/{prestamo_id}/devolver")
@router.post("/prestamos/{prestamo_id}/devolver/")
def devolver_prestamo(prestamo_id: int, db: Session = Depends(get_db)):
    prestamo = db.query(PrestamoLibro).filter(PrestamoLibro.id == prestamo_id).first()
    if not prestamo:
        raise HTTPException(status_code=404, detail="Préstamo no encontrado")
    if prestamo.devuelto:
        raise HTTPException(status_code=400, detail="Este préstamo ya fue devuelto")
    
    prestamo.devuelto = True
    prestamo.estado = "devuelto"
    prestamo.fecha_devolucion = datetime.now().strftime("%Y-%m-%d")
    
    libro = db.query(Libro).filter(Libro.id == prestamo.libro_id).first()
    if libro:
        libro.copias_disponibles = min(libro.copias_disponibles + 1, libro.copias_totales)
        
    db.commit()

    titulo_libro = libro.titulo if libro else "el libro"
    _notificar_usuario(
        db=db,
        user_id=prestamo.user_id,
        title="✅ Libro devuelto con éxito",
        message=f"Devolviste '{titulo_libro}' a la Biblioteca. ¡Muchas gracias!",
        tipo="biblioteca"
    )
    return {"status": "ok", "message": "Libro devuelto con éxito", "estado": "devuelto"}

@router.put("/libros/{libro_id}/agregar-copias")
@router.put("/libros/{libro_id}/agregar-copias/")
def agregar_copias(libro_id: int, data: AgregarCopiasData, db: Session = Depends(get_db)):
    """Agrega más copias a un libro existente."""
    libro = db.query(Libro).filter(Libro.id == libro_id).first()
    if not libro:
        raise HTTPException(status_code=404, detail="Libro no encontrado")
    if data.cantidad <= 0:
        raise HTTPException(status_code=400, detail="La cantidad debe ser mayor a 0")
    libro.copias_totales += data.cantidad
    libro.copias_disponibles += data.cantidad
    db.commit()
    db.refresh(libro)
    return libro
