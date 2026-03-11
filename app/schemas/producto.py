from pydantic import BaseModel
from typing import Any, Dict, Optional

class ProductoCreate(BaseModel):
    nombre: str
    codigo: str
    precio_actual: float
    activo: bool = True

class ProductoUpdate(BaseModel):
    precio_actual: float

class ProductoResponse(ProductoCreate):
    id: int
    class Config:
        from_attributes = True