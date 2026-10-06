from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.core.security import get_current_user_db as get_current_user
from app.modules.users.users.models import User
from . import models, schemas
import csv
from io import StringIO
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/olimpiadas", tags=["olimpiadas"])

@router.get("/activas", response_model=schemas.OlimpiadasActivasResponse)
def get_olimpiadas_activas(db: Session = Depends(get_db)):
    olimpiadas = db.query(models.Olimpiada).filter(models.Olimpiada.activa == True).all()
    categorias = db.query(models.CategoriaOlimpiada).all()
    tipos = db.query(models.TipoOlimpiada).all()
    
    return {
        "olimpiadas": olimpiadas,
        "categorias": categorias,
        "tipos": tipos
    }

@router.post("/inscripcion", response_model=schemas.InscripcionResponse)
def inscribir_olimpiada(
    inscripcion: schemas.InscripcionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verificar si ya esta inscripto a esa olimpiada, categoria y tipo
    existente = db.query(models.InscripcionOlimpiada).filter(
        models.InscripcionOlimpiada.user_id == current_user.id,
        models.InscripcionOlimpiada.olimpiada_id == inscripcion.olimpiada_id,
    ).first()
    
    if existente:
        raise HTTPException(status_code=400, detail="Ya te encuentras inscripto en esta Olimpiada.")
        
    nueva_inscripcion = models.InscripcionOlimpiada(
        user_id=current_user.id,
        olimpiada_id=inscripcion.olimpiada_id,
        categoria_id=inscripcion.categoria_id,
        tipo_id=inscripcion.tipo_id
    )
    
    db.add(nueva_inscripcion)
    db.commit()
    db.refresh(nueva_inscripcion)
    
    return nueva_inscripcion

@router.get("/admin/export")
def export_inscripciones_excel(db: Session = Depends(get_db)): # TODO: add admin dependency
    inscripciones = db.query(models.InscripcionOlimpiada).all()
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Nombre Alumno", "Email", "DNI", "Olimpiada", "Categoria", "Tipo", "Fecha Inscripcion"])
    
    for ins in inscripciones:
        writer.writerow([
            ins.id,
            ins.user.name if ins.user else "N/A",
            ins.user.email if ins.user else "N/A",
            ins.user.dni if ins.user else "N/A",
            ins.olimpiada.nombre if ins.olimpiada else "N/A",
            ins.categoria.nombre if ins.categoria else "N/A",
            ins.tipo.nombre if ins.tipo else "N/A",
            ins.fecha_inscripcion.strftime("%Y-%m-%d %H:%M:%S")
        ])
        
    output.seek(0)
    
    response = StreamingResponse(iter([output.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=inscripciones_olimpiadas.csv"
    return response
