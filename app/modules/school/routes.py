from fastapi import APIRouter
from app.core.school_config import get_school_config, reload_school_config

router = APIRouter(prefix="/school", tags=["School Config"])

@router.get("/config")
def get_config():
    cfg = get_school_config()
    return {
        "name": cfg.name, "short_name": cfg.short_name, "slogan": cfg.slogan,
        "domain": cfg.domain, "logo": cfg.logo, "favicon": cfg.favicon,
        "primary_color": cfg.primary_color, "secondary_color": cfg.secondary_color,
        "font_family": cfg.font_family, "address": cfg.address, "phone": cfg.phone,
        "email": cfg.email, "modules": cfg.modules,
        "panol_use_barcodes": cfg.panol_use_barcodes,
        "login": {"title": cfg.login_title, "subtitle": cfg.login_subtitle, "background_color": cfg.login_bg_color},
        "footer": {"text": cfg.footer_text, "show_powered_by": cfg.show_powered_by},
        "dashboards": cfg.dashboards,
        "files": {"max_size_mb": cfg.max_file_size_mb, "allowed_types": cfg.allowed_file_types},
    }

@router.post("/config/reload")
def reload_config():
    cfg = reload_school_config()
    return {"status": "ok", "school": cfg.name}

from fastapi.responses import StreamingResponse
import io
import boto3
from botocore.client import Config
from fastapi import HTTPException
from app.core.s3_client import R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT_URL

@router.get("/logo/")
@router.get("/logo")
def get_school_logo():
    s3_local = boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT_URL,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto"
    )
    try:
        # Fetch icono.jpeg from the private bucket mitecnica-app
        obj = s3_local.get_object(Bucket="mitecnica-app", Key="icono.jpeg")
        return StreamingResponse(obj['Body'], media_type="image/jpeg")
    except Exception as e:
        # Fallback to local logo
        try:
            with open("media/logo.png", "rb") as fallback:
                return StreamingResponse(io.BytesIO(fallback.read()), media_type="image/png")
        except:
            raise HTTPException(status_code=404, detail="Logo no encontrado")

