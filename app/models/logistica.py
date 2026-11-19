from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Date, Time, JSON, Enum, UniqueConstraint, Boolean, false
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.db.base import Base

class MetodoPago(str, enum.Enum):
    EFECTIVO = "efectivo"
    TRANSFERENCIA = "transferencia"
    CTA_CORRIENTE = "cta_corriente"

class RolTurno(str, enum.Enum):
    CONDUCTOR = "conductor"
    AYUDANTE = "ayudante"  # descarga

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

    # Visita excepcional: entrega a un cliente que NO esta en el recorrido sobre el que
    # se registra. Queda marcada para verla en el historial y en la auditoria de caja.
    visita_excepcional = Column(Boolean, nullable=False, default=False, server_default=false())


class Turno(Base):
    """Calendario operativo: la ruta sale `fecha` de `hora_desde` a `hora_hasta`."""
    __tablename__ = "turnos_recorrido"
    __table_args__ = (
        # Una ruta tiene a lo sumo un turno por dia.
        UniqueConstraint("tenant_id", "recorrido_id", "fecha", name="uq_turno_recorrido_fecha"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=False)
    recorrido_id = Column(Integer, ForeignKey("recorridos.id", ondelete="CASCADE"), nullable=False, index=True)
    fecha = Column(Date, nullable=False, index=True)
    hora_desde = Column(Time, nullable=False)
    hora_hasta = Column(Time, nullable=False)
    nota = Column(String(200), nullable=True)

    repartidores = relationship(
        "TurnoRepartidor", cascade="all, delete-orphan", passive_deletes=True, lazy="selectin"
    )


class TurnoRepartidor(Base):
    __tablename__ = "turnos_repartidores"
    __table_args__ = (UniqueConstraint("turno_id", "user_id", name="uq_turno_repartidor"),)

    id = Column(Integer, primary_key=True)
    turno_id = Column(Integer, ForeignKey("turnos_recorrido.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    rol = Column(Enum(RolTurno), nullable=False, default=RolTurno.AYUDANTE)

    usuario = relationship("User", lazy="joined")
