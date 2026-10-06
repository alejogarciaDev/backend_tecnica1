from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from app.core.security import get_current_user_db
from app.core.s3_client import upload_file_to_r2, list_user_files
from app.core.school_config import get_school_config

router = APIRouter(prefix="/drive", tags=["Drive"])

@router.post("/upload")
async def upload_to_drive(
    file: UploadFile = File(...),
    folder: str = Form("general"),
    user = Depends(get_current_user_db)
):
    cfg = get_school_config()
    school_prefix = cfg.id if hasattr(cfg, "id") else cfg.name.lower().replace(" ", "")
    
    try:
        object_key = upload_file_to_r2(school_prefix, user.email, file, folder)
        return {"message": "File uploaded successfully", "key": object_key}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/my-folders")
async def get_my_folders(user = Depends(get_current_user_db)):
    cfg = get_school_config()
    school_prefix = cfg.id if hasattr(cfg, "id") else cfg.name.lower().replace(" ", "")
    
    try:
        folders = list_user_files(school_prefix, user.email)
        return folders
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
