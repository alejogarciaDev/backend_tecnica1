import os
from .school_config import get_school_config

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRET_KEY = os.getenv("SECRET_KEY", os.getenv("JWT_SECRET_KEY", "sigen_clave_secreta_cambiar_en_produccion"))
ENV = os.getenv("ENV", "dev")

def get_files_path():
    cfg = get_school_config()
    path = cfg.storage_path
    if not os.path.isabs(path):
        path = os.path.join(BASE_DIR, path)
    os.makedirs(path, exist_ok=True)
    return path

def get_max_file_size():
    return get_school_config().max_file_size_mb * 1024 * 1024

def get_allowed_types():
    return get_school_config().allowed_file_types
