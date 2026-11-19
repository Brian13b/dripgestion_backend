from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, JSON, Enum, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.db.base import Base

class MetodoPago(str, enum.Enum):
    EFECTIVO = "efectivo"
    TRANSFERENCIA = "transferencia"
    CTA_CORRIENTE = "cta_corriente"

class Recorrido(Base):
    __tablename__ = "recorridos"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=False)
    
    nombre = Column(String, nullable=False) 
    dia_semana = Column(Integer) 
    
    clientes_orden = Column(JSON, default=[]) 
    
    repartidor_id = Column(Integer, ForeignKey("users.id"), nullable=True)

class Movimiento(Base):
    __tablename__ = "movimientos"
    __table_args__ = (
        # Idempotencia: la misma clave en la misma empresa identifica UNA sola operación.
        # (NULL = sin clave: no se restringe, así los clientes viejos siguen funcionando.)
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_movimientos_tenant_idempotency"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=False)
    
    cliente_id = Column(Integer, ForeignKey("clientes.id"))
    repartidor_id = Column(Integer, ForeignKey("users.id"))
    recorrido_id = Column(Integer, ForeignKey("recorridos.id"), nullable=True)
    
    fecha = Column(DateTime(timezone=True), server_default=func.now())
    
    detalles = Column(JSON, default={})
    
    monto_total = Column(Float, default=0.0)
    monto_cobrado = Column(Float, default=0.0) 
    metodo_pago = Column(Enum(MetodoPago), default=MetodoPago.EFECTIVO)
    
    observacion = Column(String, nullable=True)

    idempotency_key = Column(String(64), nullable=True)