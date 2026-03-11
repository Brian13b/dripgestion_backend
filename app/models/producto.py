from sqlalchemy import Boolean, Column, Integer, String, Float
from app.db.base import Base

class Producto(Base):
    __tablename__ = "productos"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True)
    nombre = Column(String, index=True)
    codigo = Column(String, index=True) 
    precio_actual = Column(Float, default=0.0)
    activo = Column(Boolean, default=True)