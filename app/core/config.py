import os
from .school_config import get_school_config

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRET_KEY = os.getenv("SECRET_KEY", os.getenv("JWT_SECRET_KEY", "sigen_clave_secreta_cambiar_en_produccion"))
ENV = os.getenv("ENV", "dev")

def get_files_path():
    cfg = get_school_config()
    path = os.getenv("STORAGE_PATH", getattr(cfg, "storage_path", "data/archivos"))
    if not os.path.isabs(path):
        if os.path.isdir("/app/data"):
            # En entorno Docker usamos el volumen montado en /app/data
            path = os.path.join("/app/data", os.path.basename(path))
        else:
            # Desarrollo local
            project_root = os.path.dirname(BASE_DIR) if os.path.basename(BASE_DIR) == "app" else BASE_DIR
            path = os.path.join(project_root, path)
    os.makedirs(path, exist_ok=True)
    return path

def get_max_file_size():
    return get_school_config().max_file_size_mb * 1024 * 1024

def get_allowed_types():
    return get_school_config().allowed_file_types
