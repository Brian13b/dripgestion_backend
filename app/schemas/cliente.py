import enum
from typing import Any, Dict, List, Optional
from app.models.cliente import CondicionIVA
from pydantic import BaseModel, Field, computed_field, field_validator

class EnvaseSaldoItem(BaseModel):
  tipo_envase_id: int
  nombre: str
  codigo: str
  cantidad: int
  valor_reposicion: float = 0.0
  subtotal_reposicion: float = 0.0

def _limpiar_zona(v):
  """Espacios de más fuera; vacío = sin zona."""
  if v is None:
    return None
  v = " ".join(str(v).split())
  return v or None


class ClienteBase(BaseModel):
  nombre_negocio: str
  direccion: str
  telefono: Optional[str] = None
  cuit: Optional[str] = None
  condicion_iva: Optional[CondicionIVA] = CondicionIVA.CONSUMIDOR_FINAL
  observaciones: Optional[str] = None
  zona: Optional[str] = Field(default=None, max_length=60)
  latitud: Optional[float] = None
  longitud: Optional[float] = None

  @field_validator("zona")
  @classmethod
  def _zona(cls, v):
    return _limpiar_zona(v)

class ClienteCreate(ClienteBase):
  pin_acceso: str = "1234"

class ClienteUpdate(BaseModel):
  nombre_negocio: Optional[str] = None
  direccion: Optional[str] = None
  telefono: Optional[str] = None
  observaciones: Optional[str] = None
  zona: Optional[str] = Field(default=None, max_length=60)
  pin_acceso: Optional[str] = None
  cuit: Optional[str] = None
  condicion_iva: Optional[CondicionIVA] = None
  latitud: Optional[float] = None
  longitud: Optional[float] = None
  orden_visita_default: Optional[int] = None

  @field_validator("zona")
  @classmethod
  def _zona(cls, v):
    return _limpiar_zona(v)

class ClienteResponse(ClienteBase):
  id: int
  tenant_id: int
  saldo_dinero: float
  stock_envases: Dict[str, Any] = {}
  envases_detalle: List[EnvaseSaldoItem] = []
  orden_visita_default: int
  pin_acceso: Optional[str] = Field(default=None, exclude=True)

  @computed_field
  @property
  def has_pin(self) -> bool:
    return bool(self.pin_acceso)

  class Config:
    from_attributes = True

class ClienteListResponse(BaseModel):
  total: int
  items: List[ClienteResponse]

  class Config:
    from_attributes = True