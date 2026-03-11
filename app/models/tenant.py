from sqlalchemy import Column, Integer, String, Boolean
from app.db.base import Base

class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    subdominio = Column(String, unique=True, index=True, nullable=False)
    
    # --- Branding Dinámico ---
    logo_url = Column(String, nullable=True)
    color_primario = Column(String, default="#25A7DA")
    color_secundario = Column(String, default="#0C4A6E")
    whatsapp = Column(String, nullable=True)
    
    is_active = Column(Boolean, default=True)