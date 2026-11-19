from datetime import date, datetime, time
from typing import Any, Dict, List, Literal, Optional
from app.models.logistica import MetodoPago, RolTurno
from pydantic import BaseModel, Field, field_validator, model_validator

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
  # None = dejar la ruta sin chofer habitual
  repartidor_id: Optional[int] = None

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

  # El repartidor declara que el cliente no esta en el recorrido (visita excepcional).
  visita_excepcional: bool = False

  @model_validator(mode="after")
  def _cuenta_corriente_no_se_cobra_en_el_acto(self):
    """Una entrega a cuenta corriente es 100% fiado: lo que se cobra en el acto
    se registra con su método (efectivo/transferencia). Evita cobros sin método,
    que no sumaban en ninguna columna del cierre de caja."""
    if self.metodo_pago == MetodoPago.CTA_CORRIENTE and self.monto_cobrado != 0:
      raise ValueError(
          "Una entrega a cuenta corriente no puede tener monto cobrado: "
          "elegí efectivo o transferencia para la parte cobrada"
      )
    return self

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
  metodo_pago: Literal["efectivo", "transferencia"]
  observacion: str = ""


# --- CALENDARIO OPERATIVO (turnos) ---
class TurnoRepartidorIn(BaseModel):
  user_id: int
  rol: RolTurno = RolTurno.AYUDANTE


def _validar_equipo_y_horas(desde, hasta, repartidores):
  if desde is not None and hasta is not None and desde >= hasta:
    raise ValueError("La hora de inicio debe ser anterior a la de fin")
  if repartidores is not None:
    if not 1 <= len(repartidores) <= 3:
      raise ValueError("Un turno lleva de 1 a 3 repartidores")
    if len({r.user_id for r in repartidores}) != len(repartidores):
      raise ValueError("Un repartidor no puede repetirse en el mismo turno")
    if sum(1 for r in repartidores if r.rol == RolTurno.CONDUCTOR) != 1:
      raise ValueError("El turno necesita exactamente un conductor; los demás ayudan a descargar")


class TurnoBase(BaseModel):
  hora_desde: time
  hora_hasta: time
  repartidores: List[TurnoRepartidorIn]
  nota: Optional[str] = Field(default=None, max_length=200)

  @model_validator(mode="after")
  def _validar(self):
    _validar_equipo_y_horas(self.hora_desde, self.hora_hasta, self.repartidores)
    return self


class TurnoCreate(TurnoBase):
  recorrido_id: int
  fecha: date


class TurnoUpdate(BaseModel):
  hora_desde: Optional[time] = None
  hora_hasta: Optional[time] = None
  repartidores: Optional[List[TurnoRepartidorIn]] = None
  nota: Optional[str] = Field(default=None, max_length=200)

  @model_validator(mode="after")
  def _validar(self):
    _validar_equipo_y_horas(self.hora_desde, self.hora_hasta, self.repartidores)
    return self


class ProgramarTurnos(TurnoBase):
  """Programación en lote: la ruta sale los `dias_semana` (0=lunes … 6=domingo) entre dos fechas."""
  recorrido_id: int
  fecha_desde: date
  fecha_hasta: date
  dias_semana: List[int] = Field(min_length=1)

  @field_validator("dias_semana")
  @classmethod
  def _dias_validos(cls, v):
    if any(d < 0 or d > 6 for d in v):
      raise ValueError("Los días de la semana van de 0 (lunes) a 6 (domingo)")
    return sorted(set(v))


class TurnoRepartidorOut(BaseModel):
  user_id: int
  nombre: str
  rol: RolTurno


class TurnoResponse(BaseModel):
  id: int
  recorrido_id: int
  recorrido_nombre: str
  fecha: date
  hora_desde: time
  hora_hasta: time
  nota: Optional[str] = None
  repartidores: List[TurnoRepartidorOut]


class OmisionProgramacion(BaseModel):
  fecha: date
  motivo: str


class ProgramarTurnosResponse(BaseModel):
  creados: int
  omitidos: List[OmisionProgramacion]
