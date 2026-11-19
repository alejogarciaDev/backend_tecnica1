from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import get_files_path, get_max_file_size, get_allowed_types
from app.core.security import get_current_user_db
from .models import Archivo
import os, uuid

router = APIRouter(prefix="/archivos", tags=["Archivos"])

BLOCKED_EXTENSIONS = {".exe", ".bat", ".cmd", ".sh", ".php", ".py", ".js", ".html", ".htm", ".vbs", ".ps1", ".svg"}

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    alumno_id: int = Form(None),
    materia_id: int = Form(None),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_db)
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext in BLOCKED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Tipo de archivo no permitido por motivos de seguridad.")

    content_type = file.content_type
    if not content_type or content_type == "application/octet-stream":
        import mimetypes
        guess, _ = mimetypes.guess_type(file.filename)
        if guess:
            content_type = guess
        else:
            content_type = "application/octet-stream"
    
    content = await file.read()
    max_size = max(get_max_file_size(), 100 * 1024 * 1024) # Hasta 100MB
    if len(content) > max_size:
        raise HTTPException(status_code=400, detail="Archivo demasiado grande")
        
    unique_name = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(get_files_path(), unique_name)
    with open(file_path, "wb") as f:
        f.write(content)
        
    archivo = Archivo(
        alumno_id=alumno_id,
        materia_id=materia_id,
        nombre_archivo=file.filename,
        ruta_archivo=file_path,
        tipo=content_type
    )
    db.add(archivo)
    db.commit()
    db.refresh(archivo)
    return archivo

@router.get("/alumno/{alumno_id}")
def get_alumno_files(alumno_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user_db)):
    return db.query(Archivo).filter(Archivo.alumno_id == alumno_id).all()

@router.get("/file/{archivo_id}")
def get_file(archivo_id: int, inline: bool = False, db: Session = Depends(get_db), current_user = Depends(get_current_user_db)):
    archivo = db.query(Archivo).filter(Archivo.id == archivo_id).first()
    if not archivo:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    if not os.path.exists(archivo.ruta_archivo):
        raise HTTPException(status_code=404, detail="Archivo físico no encontrado en el servidor")
    disposition = "inline" if inline else "attachment"
    return FileResponse(archivo.ruta_archivo, media_type=archivo.tipo, filename=archivo.nombre_archivo, content_disposition_type=disposition)

@router.get("/view/{archivo_id}")
def view_file_alias(archivo_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user_db)):
    return get_file(archivo_id, inline=True, db=db, current_user=current_user)

@router.get("/descargar/{archivo_id}")
def descargar_file_alias(archivo_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user_db)):
    return get_file(archivo_id, inline=False, db=db, current_user=current_user)

