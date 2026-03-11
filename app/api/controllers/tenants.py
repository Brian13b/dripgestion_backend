from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.tenant import TenantResponse
from app.services import tenant_service

router = APIRouter()

@router.get("/info/{subdominio}", response_model=TenantResponse)
def get_tenant_info(subdominio: str, db: Session = Depends(get_db)):
    """
    Ruta pública para obtener los colores y logo de la empresa antes de iniciar sesión.
    """
    try:
        return tenant_service.obtener_info_tenant(db, subdominio)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))