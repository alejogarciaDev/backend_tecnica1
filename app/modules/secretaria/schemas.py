from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class AlumnoPreRegistro(BaseModel):
    dni: str
    nombre: str
    apellido: str
    fecha_nacimiento: str # DD/MM/AAAA or YYYY-MM-DD
    curso: str # e.g. "5°"
    division: str # e.g. "2°"
    turno: str # Mañana, Tarde, Vespertino, Doble
    estado_academico: Optional[str] = "REGULAR" # REGULAR, INACTIVO, EGRESADO, DADO_DE_BAJA
    telefono: Optional[str] = None
    folio: Optional[str] = None
    legajo: Optional[str] = None
    grupo_taller: Optional[str] = None

class AlumnoUpdateSecretaria(BaseModel):
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    fecha_nacimiento: Optional[str] = None
    curso: Optional[str] = None
    division: Optional[str] = None
    turno: Optional[str] = None
    telefono: Optional[str] = None
    folio: Optional[str] = None
    legajo: Optional[str] = None
    grupo_taller: Optional[str] = None

class EstadoAcademicoUpdate(BaseModel):
    estado_academico: str # REGULAR, INACTIVO, EGRESADO, DADO_DE_BAJA
    motivo: Optional[str] = None

class BloqueoCuentaUpdate(BaseModel):
    bloqueada: bool
    motivo: Optional[str] = None

class ResetPasswordRequest(BaseModel):
    new_password: Optional[str] = None
    must_change_password: bool = True

class AlumnoSecretariaOut(BaseModel):
    id: int
    dni: str
    nombre: str
    apellido: str
    fecha_nacimiento: Optional[str] = None
    curso: Optional[str] = None
    division: Optional[str] = None
    turno: Optional[str] = None
    grupo_taller: Optional[str] = None
    folio: Optional[str] = None
    legajo: Optional[str] = None
    telefono: Optional[str] = None
    estado_academico: str
    estado_cuenta: str
    estado_identidad: str
    user_id: Optional[int] = None
    school_id: Optional[int] = None
    temp_password: Optional[str] = None

    class Config:
        from_attributes = True

class SecretariaMetricas(BaseModel):
    total_alumnos: int
    regulares: int
    inactivos: int
    egresados: int
    dados_de_baja: int
    cuentas_activas: int
    cuentas_sin_activar: int
    cuentas_bloqueadas: int

class AuditLogItem(BaseModel):
    id: int
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    user_role: Optional[str] = None
    action: str
    target_id: Optional[int] = None
    target_dni: Optional[str] = None
    target_name: Optional[str] = None
    details: Optional[str] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True
