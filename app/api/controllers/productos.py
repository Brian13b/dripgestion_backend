from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api import deps
from app.crud import crud_producto
from app.db.session import get_db
from app.models.user import User
from app.schemas.producto import (ProductoCreate, ProductoResponse, ProductoUpdate, TipoEnvaseCreate, TipoEnvaseResponse, TipoEnvaseUpdate)
from app.services import producto_service

router = APIRouter()


# --- ENDPOINTS TIPOS DE ENVASE ---
@router.get("/tipos-envase", response_model=list[TipoEnvaseResponse])
def get_tipos_envase(
    solo_activos: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
):
  return crud_producto.get_tipos_envase_by_tenant(
      db, current_user.tenant_id, solo_activos=solo_activos
  )


@router.post("/tipos-envase", response_model=TipoEnvaseResponse)
def create_tipo_envase(
    envase_in: TipoEnvaseCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(deps.get_current_admin),
):
  try:
    return producto_service.crear_tipo_envase(
        db, envase_in, current_admin.tenant_id
    )
  except ValueError as e:
    raise HTTPException(status_code=400, detail=str(e))


@router.put("/tipos-envase/{tipo_envase_id}", response_model=TipoEnvaseResponse)
def update_tipo_envase(
    tipo_envase_id: int,
    envase_in: TipoEnvaseUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(deps.get_current_admin),
):
  try:
    return producto_service.actualizar_tipo_envase(
        db, tipo_envase_id, envase_in, current_admin.tenant_id
    )
  except ValueError as e:
    raise HTTPException(status_code=404, detail=str(e))


@router.put(
    "/tipos-envase/{tipo_envase_id}/toggle", response_model=TipoEnvaseResponse
)
def toggle_tipo_envase(
    tipo_envase_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(deps.get_current_admin),
):
  try:
    return producto_service.alternar_estado_tipo_envase(
        db, tipo_envase_id, current_admin.tenant_id
    )
  except ValueError as e:
    raise HTTPException(status_code=404, detail=str(e))


# --- ENDPOINTS PRODUCTOS ---
@router.get("", response_model=list[ProductoResponse])
def get_productos(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
):
  return crud_producto.get_productos_by_tenant(db, current_user.tenant_id)


@router.post("", response_model=ProductoResponse)
def create_producto(
    prod_in: ProductoCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(deps.get_current_admin),
):
  try:
    return producto_service.crear_producto(
        db, prod_in, current_admin.tenant_id
    )
  except ValueError as e:
    raise HTTPException(status_code=400, detail=str(e))


@router.put("/{producto_id}", response_model=ProductoResponse)
def update_producto(
    producto_id: int,
    prod_in: ProductoUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(deps.get_current_admin),
):
  try:
    return producto_service.actualizar_producto(
        db, producto_id, prod_in, current_admin.tenant_id
    )
  except ValueError as e:
    status_code = 404 if "no encontrado" in str(e).lower() else 400
    raise HTTPException(status_code=status_code, detail=str(e))


@router.put("/{producto_id}/toggle", response_model=ProductoResponse)
def toggle_activo(
    producto_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(deps.get_current_admin),
):
  try:
    return producto_service.alternar_estado_producto(
        db, producto_id, current_admin.tenant_id
    )
  except ValueError as e:
    raise HTTPException(status_code=404, detail=str(e))