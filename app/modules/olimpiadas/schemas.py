from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class OlimpiadaBase(BaseModel):
    nombre: str
    activa: bool = True

class OlimpiadaResponse(OlimpiadaBase):
    id: int
    fecha_creacion: datetime

    class Config:
        orm_mode = True

class CategoriaOlimpiadaResponse(BaseModel):
    id: int
    nombre: str

    class Config:
        orm_mode = True

class TipoOlimpiadaResponse(BaseModel):
    id: int
    nombre: str

    class Config:
        orm_mode = True

class InscripcionCreate(BaseModel):
    olimpiada_id: int
    categoria_id: int
    tipo_id: int

class InscripcionResponse(BaseModel):
    id: int
    user_id: int
    olimpiada_id: int
    categoria_id: int
    tipo_id: int
    fecha_inscripcion: datetime

    class Config:
        orm_mode = True

class OlimpiadasActivasResponse(BaseModel):
    olimpiadas: List[OlimpiadaResponse]
    categorias: List[CategoriaOlimpiadaResponse]
    tipos: List[TipoOlimpiadaResponse]
