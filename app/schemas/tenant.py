from typing import Optional
from pydantic import BaseModel

class TenantBase(BaseModel):
    nombre: str
    subdominio: str
    logo_url: Optional[str] = None
    color_primario: str = "#25A7DA"
    color_secundario: str = "#0C4A6E"
    whatsapp: Optional[str] = None
    is_active: bool = True

class TenantCreate(TenantBase):
    pass

class TenantUpdate(BaseModel):
    nombre: Optional[str] = None
    subdominio: Optional[str] = None
    logo_url: Optional[str] = None
    color_primario: Optional[str] = None
    color_secundario: Optional[str] = None
    is_active: Optional[bool] = None

class TenantResponse(TenantBase):
    id: int

    class Config:
        from_attributes = True