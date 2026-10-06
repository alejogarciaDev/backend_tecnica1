import os
from jose import jwt, JWTError
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import SECRET_KEY, ENV

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("TOKEN_EXPIRE_MINUTES", "525600"))
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    if not token:
        raise HTTPException(status_code=401, detail="Token requerido")
    clean_token = token.strip()
    if clean_token.lower().startswith("bearer "):
        clean_token = clean_token[7:].strip()
    try:
        return jwt.decode(clean_token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = decode_token(token)
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Token inválido")
    return {"id": int(user_id), "role": payload.get("role"), "role_name": payload.get("role_name")}

def get_current_user_db(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    payload = decode_token(token)
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Token inválido")
    from app.modules.users.users.models import User
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    return user

import bcrypt

def hash_password(password: str) -> str:
    if not password:
        return ""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8")[:72], salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not plain_password or not hashed_password:
        return False
    # Backwards compatibility check for existing plain-text passwords
    if not hashed_password.startswith("$2b$") and not hashed_password.startswith("$2a$"):
        return plain_password == hashed_password
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8")[:72], hashed_password.encode("utf-8"))
    except Exception:
        return False

def generate_temp_password(fecha_nacimiento: str, dni: str) -> str:
    """Generates student initial temporary password: DDMMAAAA + last 4 digits of DNI."""
    dni_digits = "".join(filter(str.isdigit, str(dni)))
    last4 = dni_digits[-4:] if len(dni_digits) >= 4 else dni_digits.zfill(4)
    raw_date = str(fecha_nacimiento or "").strip()
    
    if "-" in raw_date and raw_date.split("-")[0].isdigit() and len(raw_date.split("-")[0]) == 4:
        parts = raw_date.split("-")
        date_part = f"{parts[2].zfill(2)}{parts[1].zfill(2)}{parts[0]}"
    elif "/" in raw_date:
        parts = raw_date.split("/")
        if len(parts) == 3:
            if len(parts[2]) == 4: # DD/MM/YYYY
                date_part = f"{parts[0].zfill(2)}{parts[1].zfill(2)}{parts[2]}"
            else: # YYYY/MM/DD
                date_part = f"{parts[2].zfill(2)}{parts[1].zfill(2)}{parts[0]}"
        else:
            date_part = "".join(filter(str.isdigit, raw_date))
    else:
        date_part = "".join(filter(str.isdigit, raw_date))
        
    return f"{date_part}{last4}"

def require_permission(permission_name: str):
    def permission_checker(user=Depends(get_current_user_db)):
        user_role = (user.role.name if user.role and user.role.name else "").lower().strip()
        
        # 1. Alumnos are strictly alumnos: deny any administrative or management access
        if user_role == "alumno":
            allowed_alumno_prefixes = ("entregas.", "misdocumentos.", "calificaciones.ver", "horarios.ver", "boletines.ver", "materias.ver", "campus.ver")
            if not any(permission_name.startswith(p) for p in allowed_alumno_prefixes):
                raise HTTPException(status_code=403, detail="Acceso denegado. Los alumnos solo pueden acceder a sus propios módulos estudiantiles.")
                
        # 2. Admin cannot create or directly alter student academic onboarding
        secretaria_restricted_perms = ("alumnos.create", "alumnos.pre_registro", "alumnos.delete", "alumnos.manage_academic", "secretaria.")
        if any(permission_name.startswith(p) for p in secretaria_restricted_perms):
            if user_role == "admin":
                raise HTTPException(
                    status_code=403, 
                    detail="No autorizado. El rol Administrador no tiene permisos para crear alumnos ni administrar altas académicas. Esta función corresponde a Secretaría."
                )

        # 3. Superadmin bypasses other restrictions
        if user_role == "superadmin":
            return user
            
        # 4. Admin bypasses non-secretaria general permissions
        if user_role == "admin":
            return user

        # 5. Secretaria and oficina_alumnos roles are authorized for all secretaria.* and alumnos.* operations
        if (user_role in ("secretaria", "oficina_alumnos")) and (permission_name.startswith("secretaria.") or permission_name.startswith("alumnos.")):
            return user

        # 6. Check role-level and user-level permissions
        role_perms = {p.name for p in user.role.permissions} if user.role else set()
        user_perms = {p.name for p in user.permissions}
        all_perms = role_perms | user_perms
        if permission_name not in all_perms and "*" not in all_perms:
            has_wildcard = False
            for p in all_perms:
                if p.endswith(".*") and permission_name.startswith(p[:-2]):
                    has_wildcard = True
                    break
            if not has_wildcard:
                raise HTTPException(status_code=403, detail=f"No autorizado. Se requiere permiso: {permission_name}")
        return user
    return permission_checker

def require_role(role_name: str):
    def role_checker(user=Depends(get_current_user_db)):
        current_role = (user.role.name if user.role else "").lower().strip()
        target_role = role_name.lower().strip()
        if current_role != target_role:
            raise HTTPException(status_code=403, detail=f"No autorizado. Se requiere rol: {role_name}")
        return user
    return role_checker

def require_admin(user=Depends(get_current_user_db)):
    current_role = (user.role.name if user.role else "").lower().strip()
    if current_role not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="No autorizado (solo admin)")
    return user
