from datetime import datetime
from typing import Any, Dict, List, Optional
from app.models.logistica import MetodoPago
from pydantic import BaseModel, Field, field_validator

class RecorridoBase(BaseModel):
  nombre: str
  dia_semana: int
  repartidor_id: Optional[int] = None

class RecorridoCreate(RecorridoBase):
  clientes_orden: Optional[List[int]] = []

class RecorridoUpdate(BaseModel):
  nombre: Optional[str] = None
  clientes_orden: Optional[List[int]] = None

class RecorridoAsignarRepartidor(BaseModel):
  repartidor_id: int

class RecorridoResponse(RecorridoBase):
  id: int
  tenant_id: int
  clientes_orden: List[int]

  class Config:
    from_attributes = True

# --- MOVIMIENTOS ---
class MovimientoCreate(BaseModel):
  cliente_id: int
  recorrido_id: Optional[int] = None

  detalles: Dict[str, Any] = Field(default_factory=dict)

  devoluciones_envases: Optional[Dict[str, int]] = None

  monto_total: float = Field(ge=0)
  monto_cobrado: float = Field(ge=0)
  metodo_pago: MetodoPago
  observacion: Optional[str] = None

  @field_validator("devoluciones_envases")
  @classmethod
  def _devoluciones_no_negativas(cls, v):
    if v and any(cant < 0 for cant in v.values()):
      raise ValueError("Las cantidades de envases devueltos no pueden ser negativas")
    return v

  @field_validator("detalles")
  @classmethod
  def _detalles_validos(cls, v):
    """Cada producto debe traer cantidades numéricas enteras y no negativas."""
    for producto_id, cant in v.items():
      valores = (
          [cant.get("entregado", 0), cant.get("devuelto", 0)]
          if isinstance(cant, dict)
          else [cant]
      )
      for valor in valores:
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
          raise ValueError(f"Cantidad inválida para el producto {producto_id}")
        if valor < 0 or int(valor) != valor:
          raise ValueError(
              f"La cantidad del producto {producto_id} debe ser un entero mayor o igual a 0"
          )
    return v

class MovimientoResponse(MovimientoCreate):
  id: int
  fecha: datetime
  repartidor_id: int

  class Config:
    from_attributes = True

class PagoManualCreate(BaseModel):
  monto: float = Field(gt=0)
  metodo_pago: str
  observacion: str = ""