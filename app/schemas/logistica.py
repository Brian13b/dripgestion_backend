from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from datetime import datetime
from app.models.logistica import MetodoPago

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
    
    detalles: Dict[str, Any]
    
    monto_total: float
    monto_cobrado: float
    metodo_pago: MetodoPago
    observacion: Optional[str] = None

class MovimientoResponse(MovimientoCreate):
    id: int
    fecha: datetime
    repartidor_id: int
    
    class Config:
        from_attributes = True

class PagoManualCreate(BaseModel):
    monto: float
    metodo_pago: str
    observacion: str = ""