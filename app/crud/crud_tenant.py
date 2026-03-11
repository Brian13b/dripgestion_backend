from sqlalchemy.orm import Session
from app.models.tenant import Tenant

def get_tenant_by_subdomain(db: Session, subdominio: str):
    return db.query(Tenant).filter(
        Tenant.subdominio == subdominio, 
        Tenant.is_active == True
    ).first()