from sqlalchemy.orm import Session
from app.crud import crud_producto
from app.schemas.producto import (ProductoCreate, ProductoUpdate, TipoEnvaseCreate, TipoEnvaseUpdate)


# --- TIPOS DE ENVASE ---
def crear_tipo_envase(db: Session, envase_in: TipoEnvaseCreate, tenant_id: int):
  codigo_norm = envase_in.codigo.upper().strip()
  existente = crud_producto.get_tipo_envase_by_codigo(
      db, codigo_norm, tenant_id
  )
  if existente:
    raise ValueError("Ya existe un tipo de envase con ese código")
  return crud_producto.create_tipo_envase(db, envase_in, tenant_id)


def actualizar_tipo_envase(
    db: Session,
    tipo_envase_id: int,
    envase_in: TipoEnvaseUpdate,
    tenant_id: int,
):
  tipo_envase = crud_producto.get_tipo_envase_by_id(
      db, tipo_envase_id, tenant_id
  )
  if not tipo_envase:
    raise ValueError("Tipo de envase no encontrado")

  update_data = envase_in.model_dump(exclude_unset=True)
  for field, value in update_data.items():
    setattr(tipo_envase, field, value)

  return crud_producto.update_tipo_envase_db(db, tipo_envase)


def alternar_estado_tipo_envase(
    db: Session, tipo_envase_id: int, tenant_id: int
):
  tipo_envase = crud_producto.get_tipo_envase_by_id(
      db, tipo_envase_id, tenant_id
  )
  if not tipo_envase:
    raise ValueError("Tipo de envase no encontrado")

  tipo_envase.activo = not tipo_envase.activo
  return crud_producto.update_tipo_envase_db(db, tipo_envase)


# --- PRODUCTOS ---
def _validar_envase_producto(
    db: Session,
    es_retornable: bool,
    tipo_envase_id: int | None,
    tenant_id: int,
):
  if es_retornable:
    if not tipo_envase_id:
      raise ValueError(
          "Los productos retornables deben tener un tipo de envase asignado"
      )
    envase = crud_producto.get_tipo_envase_by_id(db, tipo_envase_id, tenant_id)
    if not envase:
      raise ValueError("El tipo de envase seleccionado no existe")
    if not envase.activo:
      raise ValueError("El tipo de envase seleccionado está inactivo")


def crear_producto(db: Session, prod_in: ProductoCreate, tenant_id: int):
  codigo_norm = prod_in.codigo.upper().strip()
  producto_existente = crud_producto.get_producto_by_codigo(
      db, codigo_norm, tenant_id
  )
  if producto_existente:
    raise ValueError("Ya existe un producto con ese código")

  _validar_envase_producto(
      db, prod_in.es_retornable, prod_in.tipo_envase_id, tenant_id
  )
  return crud_producto.create_producto(db, prod_in, tenant_id)


def actualizar_producto(
    db: Session, producto_id: int, prod_in: ProductoUpdate, tenant_id: int
):
  producto = crud_producto.get_producto_by_id(db, producto_id, tenant_id)
  if not producto:
    raise ValueError("Producto no encontrado")

  update_data = prod_in.model_dump(exclude_unset=True)

  if "codigo" in update_data and update_data["codigo"]:
    nuevo_codigo = update_data["codigo"].upper().strip()
    existente = crud_producto.get_producto_by_codigo(
        db, nuevo_codigo, tenant_id
    )
    if existente and existente.id != producto_id:
      raise ValueError("Ya existe otro producto con ese código")
    update_data["codigo"] = nuevo_codigo

  if "unidad_medida" in update_data and update_data["unidad_medida"]:
    update_data["unidad_medida"] = update_data["unidad_medida"].value

  es_retornable_final = update_data.get("es_retornable", producto.es_retornable)
  tipo_envase_final = update_data.get(
      "tipo_envase_id", producto.tipo_envase_id
  )

  if not es_retornable_final:
    update_data["tipo_envase_id"] = None
  else:
    _validar_envase_producto(db, True, tipo_envase_final, tenant_id)

  for field, value in update_data.items():
    setattr(producto, field, value)

  return crud_producto.update_producto_db(db, producto)


def alternar_estado_producto(db: Session, producto_id: int, tenant_id: int):
  producto = crud_producto.get_producto_by_id(db, producto_id, tenant_id)
  if not producto:
    raise ValueError("Producto no encontrado")

  producto.activo = not producto.activo
  return crud_producto.update_producto_db(db, producto)