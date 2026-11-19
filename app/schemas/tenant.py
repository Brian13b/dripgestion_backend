from typing import Optional
from pydantic import BaseModel
from app.core import branding

class TenantBase(BaseModel):
    nombre: str
    subdominio: str
    whatsapp: Optional[str] = None
    logo_url: Optional[str] = None
    logo_public_id: Optional[str] = None
    is_active: bool = True
    font_sans: Optional[str] = branding.FONT_SANS
    color_primario: Optional[str] = branding.COLOR_PRIMARIO
    color_primario_light: Optional[str] = branding.COLOR_PRIMARIO_LIGHT
    color_primario_dark: Optional[str] = branding.COLOR_PRIMARIO_DARK
    color_background: Optional[str] = branding.COLOR_BACKGROUND
    color_success: Optional[str] = branding.COLOR_SUCCESS
    color_danger: Optional[str] = branding.COLOR_DANGER
    color_secondary: Optional[str] = branding.COLOR_SECONDARY

class TenantCreate(TenantBase):
    nombre: Optional[str] = None
    subdominio: Optional[str] = None
    whatsapp: Optional[str] = None
    logo_url: Optional[str] = None
    logo_public_id: Optional[str] = None
    is_active: Optional[bool] = None
    font_sans: Optional[str] = None
    color_primario: Optional[str] = None
    color_primario_light: Optional[str] = None
    color_primario_dark: Optional[str] = None
    color_background: Optional[str] = None
    color_success: Optional[str] = None
    color_danger: Optional[str] = None
    color_secondary: Optional[str] = None

class TenantUpdate(BaseModel):
    nombre: Optional[str] = None
    subdominio: Optional[str] = None
    whatsapp: Optional[str] = None
    logo_url: Optional[str] = None
    logo_public_id: Optional[str] = None
    font_sans: Optional[str] = None
    color_primario: Optional[str] = None
    color_primario_light: Optional[str] = None
    color_primario_dark: Optional[str] = None
    color_background: Optional[str] = None
    color_success: Optional[str] = None
    color_danger: Optional[str] = None
    color_secondary: Optional[str] = None

class TenantOnboardingCreate(BaseModel):
  # Datos de la empresa
  nombre: str
  subdominio: str
  whatsapp: Optional[str] = None
  color_primario: Optional[str] = branding.COLOR_PRIMARIO

  admin_username: str
  admin_password: str
  admin_full_name: str

class TenantResponse(TenantBase):
    id: int
    is_active: bool

    class Config:
        from_attributes = True