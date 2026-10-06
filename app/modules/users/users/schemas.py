from pydantic import BaseModel
from typing import Optional, List

class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    role_id: int
    dni: Optional[str] = None
    tipo: Optional[str] = "aula" # "aula" or "taller"
    dashboards: Optional[List[str]] = []

class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    role_id: Optional[int] = None
    dni: Optional[str] = None
    tipo: Optional[str] = None # "aula" or "taller"
    dashboards: Optional[List[str]] = None

class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role_id: Optional[int] = None
    role_name: Optional[str] = None
    dni: Optional[str] = None
    tipo: Optional[str] = None
    dashboards: List[str] = []
    class Config:
        from_attributes = True
