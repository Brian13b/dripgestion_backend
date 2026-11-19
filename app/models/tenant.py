from sqlalchemy import Column, Integer, String, Boolean
from app.core import branding
from app.db.base import Base

class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    subdominio = Column(String, unique=True, index=True, nullable=False)
    whatsapp = Column(String, nullable=True)
    
    # --- Branding Dinámico ---
    logo_url = Column(String, nullable=True)
    logo_public_id = Column(String, nullable=True)
    font_sans = Column(String, default=branding.FONT_SANS)
    color_primario = Column(String, default=branding.COLOR_PRIMARIO)
    color_primario_light = Column(String, default=branding.COLOR_PRIMARIO_LIGHT)
    color_primario_dark = Column(String, default=branding.COLOR_PRIMARIO_DARK)
    color_background = Column(String, default=branding.COLOR_BACKGROUND)
    color_success = Column(String, default=branding.COLOR_SUCCESS)
    color_danger = Column(String, default=branding.COLOR_DANGER)
    color_secondary = Column(String, default=branding.COLOR_SECONDARY)
    
    is_active = Column(Boolean, default=True)