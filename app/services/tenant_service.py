from sqlalchemy.orm import Session
from app.crud import crud_tenant

def obtener_info_tenant(db: Session, subdominio: str):
    tenant = crud_tenant.get_tenant_by_subdomain(db, subdominio)
    if not tenant:
        raise ValueError("Empresa no encontrada o inactiva")
    return tenant