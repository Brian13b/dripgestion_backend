import enum
from app.db.base import Base
from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

class UnidadMedida(str, enum.Enum):
  UNIDAD = "unidad"
  CAJA = "caja"
  CAJON = "cajon"
  PACK = "pack"
  KG = "kg"
  LITRO = "litro"

class TipoEnvase(Base):
  __tablename__ = "tipos_envase"

  id = Column(Integer, primary_key=True, index=True)
  tenant_id = Column(Integer, index=True, nullable=False)
  nombre = Column(String, nullable=False)
  codigo = Column(String, index=True, nullable=False)
  valor_reposicion = Column(Float, default=0.0)
  activo = Column(Boolean, default=True)

  productos = relationship("Producto", back_populates="tipo_envase")


class Producto(Base):
  __tablename__ = "productos"

  id = Column(Integer, primary_key=True, index=True)
  tenant_id = Column(Integer, index=True, nullable=False)
  nombre = Column(String, index=True, nullable=False)
  codigo = Column(String, index=True, nullable=False)
  precio_actual = Column(Float, default=0.0)
  activo = Column(Boolean, default=True)

  unidad_medida = Column(String, default=UnidadMedida.UNIDAD.value, nullable=False)
  es_retornable = Column(Boolean, default=False, nullable=False)
  tipo_envase_id = Column(Integer, ForeignKey("tipos_envase.id"), nullable=True)

  tipo_envase = relationship("TipoEnvase", back_populates="productos")