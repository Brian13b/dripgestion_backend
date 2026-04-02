from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.api import deps
from app.db.session import get_db
from app.models.user import User
from app.services import dashboard_service

router = APIRouter()

@router.get("/resumen")
def get_dashboard_stats(mes_a: Optional[int] = Query(None), anio_a: Optional[int] = Query(None), mes_b: Optional[int] = Query(None), anio_b: Optional[int] = Query(None), db: Session = Depends(get_db), current_admin: User = Depends(deps.get_current_admin)):
    try:
        return dashboard_service.obtener_metricas_dashboard(db, current_admin, mes_a, anio_a, mes_b, anio_b)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al calcular métricas: {str(e)}")