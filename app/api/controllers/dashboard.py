from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api import deps
from app.db.session import get_db
from app.models import user
from app.services import dashboard_service

router = APIRouter()

@router.get("/resumen")
def get_dashboard_stats(db: Session = Depends(get_db), current_user: user.User = Depends(deps.get_current_user)):
    return dashboard_service.obtener_metricas_dashboard(db, current_user.tenant_id)