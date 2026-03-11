from sqlalchemy import JSON, Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base

class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=False)
    
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=True)
    
    # Datos de negocio
    nombre_negocio = Column(String, index=True) 
    direccion = Column(String, nullable=False)
    telefono = Column(String, nullable=True)
    observaciones = Column(String, nullable=True)

    pin_acceso = Column(String, default="0000")
    
    # Saldos 
    saldo_dinero = Column(Float, default=0.0)
    stock_envases = Column(JSON, default={})
    
    # Logística
    orden_visita_default = Column(Integer, default=0) 

    # Relación inversa
    usuario = relationship("app.models.user.User", backref="perfil_cliente")