from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api import deps
from app.db.session import get_db
from app.models.user import User
from app.services import portal_service

router = APIRouter()

@router.get("/mi-cuenta")
def get_mi_cuenta(db: Session = Depends(get_db), current_user: User = Depends(deps.get_current_user)):
    try:
        return portal_service.obtener_datos_mi_cuenta(db, current_user.id, current_user.tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))