from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app import models, schemas
from app.api import deps
from app.db.session import get_db
from app.services import cliente_service

router = APIRouter()

@router.get("")
def read_clientes(db: Session = Depends(get_db), skip: int = 0, limit: int = 100, current_user: models.user.User = Depends(deps.get_current_user)):
    return cliente_service.obtener_clientes_paginados(db, current_user.tenant_id, skip, limit)

@router.post("", response_model=schemas.ClienteResponse)
def create_cliente(cliente_in: schemas.ClienteCreate, db: Session = Depends(get_db), current_user: models.user.User = Depends(deps.get_current_user)):
    try:
        return cliente_service.crear_cliente_con_acceso(db, cliente_in, current_user.tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{cliente_id}", response_model=schemas.ClienteResponse)
def read_cliente_by_id(cliente_id: int, db: Session = Depends(get_db), current_user: models.user.User = Depends(deps.get_current_user)):
    try:
        return cliente_service.obtener_cliente_por_id(db, cliente_id, current_user.tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.put("/{cliente_id}", response_model=schemas.ClienteResponse)
def update_cliente(cliente_id: int, cliente_in: schemas.ClienteUpdate, db: Session = Depends(get_db), current_user: models.user.User = Depends(deps.get_current_user)):
    try:
        return cliente_service.actualizar_cliente(db, cliente_id, cliente_in.dict(exclude_unset=True), current_user.tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/{cliente_id}")
def delete_cliente(cliente_id: int, db: Session = Depends(get_db), current_user: models.user.User = Depends(deps.get_current_user)):
    try:
        cliente_service.eliminar_cliente(db, cliente_id, current_user.tenant_id)
        return {"message": "Cliente eliminado exitosamente"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))