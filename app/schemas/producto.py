from typing import Optional
from app.models.producto import UnidadMedida
from pydantic import BaseModel

# --- TIPOS DE ENVASE ---
class TipoEnvaseBase(BaseModel):
  nombre: str
  codigo: str
  valor_reposicion: float = 0.0
  activo: bool = True

class TipoEnvaseCreate(TipoEnvaseBase):
  pass

class TipoEnvaseUpdate(BaseModel):
  nombre: Optional[str] = None
  valor_reposicion: Optional[float] = None
  activo: Optional[bool] = None

class TipoEnvaseResponse(TipoEnvaseBase):
  id: int
  tenant_id: int

  class Config:
    from_attributes = True

# --- PRODUCTOS ---
class ProductoBase(BaseModel):
  nombre: str
  codigo: str
  precio_actual: float
  activo: bool = True
  unidad_medida: UnidadMedida = UnidadMedida.UNIDAD
  es_retornable: bool = False
  tipo_envase_id: Optional[int] = None

class ProductoCreate(ProductoBase):
  pass

class ProductoUpdate(BaseModel):
  nombre: Optional[str] = None
  codigo: Optional[str] = None
  precio_actual: Optional[float] = None
  activo: Optional[bool] = None
  unidad_medida: Optional[UnidadMedida] = None
  es_retornable: Optional[bool] = None
  tipo_envase_id: Optional[int] = None

class ProductoResponse(ProductoBase):
  id: int
  tenant_id: int
  tipo_envase: Optional[TipoEnvaseResponse] = None

  class Config:
    from_attributes = True