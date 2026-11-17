from sqlalchemy.orm import Session, joinedload
from app.models.producto import Producto, TipoEnvase
from app.schemas.producto import ProductoCreate, TipoEnvaseCreate


# --- TIPOS DE ENVASE ---
def get_tipos_envase_by_tenant(
    db: Session, tenant_id: int, solo_activos: bool = False
):
  query = db.query(TipoEnvase).filter(TipoEnvase.tenant_id == tenant_id)
  if solo_activos:
    query = query.filter(TipoEnvase.activo == True)
  return query.order_by(TipoEnvase.id.asc()).all()


def get_tipo_envase_by_id(db: Session, tipo_envase_id: int, tenant_id: int):
  return (
      db.query(TipoEnvase)
      .filter(
          TipoEnvase.id == tipo_envase_id, TipoEnvase.tenant_id == tenant_id
      )
      .first()
  )


def get_tipo_envase_by_codigo(db: Session, codigo: str, tenant_id: int):
  return (
      db.query(TipoEnvase)
      .filter(TipoEnvase.codigo == codigo, TipoEnvase.tenant_id == tenant_id)
      .first()
  )


def create_tipo_envase(db: Session, envase_in: TipoEnvaseCreate, tenant_id: int):
  nuevo_envase = TipoEnvase(
      tenant_id=tenant_id,
      nombre=envase_in.nombre.strip(),
      codigo=envase_in.codigo.upper().strip(),
      valor_reposicion=envase_in.valor_reposicion,
      activo=envase_in.activo,
  )
  db.add(nuevo_envase)
  db.commit()
  db.refresh(nuevo_envase)
  return nuevo_envase


def update_tipo_envase_db(db: Session, tipo_envase: TipoEnvase):
  db.commit()
  db.refresh(tipo_envase)
  return tipo_envase


# --- PRODUCTOS ---
def get_productos_by_tenant(db: Session, tenant_id: int):
  return (
      db.query(Producto)
      .options(joinedload(Producto.tipo_envase))
      .filter(Producto.tenant_id == tenant_id)
      .order_by(Producto.id.asc())
      .all()
  )


def get_producto_by_codigo(db: Session, codigo: str, tenant_id: int):
  return (
      db.query(Producto)
      .filter(Producto.codigo == codigo, Producto.tenant_id == tenant_id)
      .first()
  )


def get_producto_by_id(db: Session, producto_id: int, tenant_id: int):
  return (
      db.query(Producto)
      .options(joinedload(Producto.tipo_envase))
      .filter(Producto.id == producto_id, Producto.tenant_id == tenant_id)
      .first()
  )


def create_producto(db: Session, prod_in: ProductoCreate, tenant_id: int):
  nuevo_producto = Producto(
      tenant_id=tenant_id,
      nombre=prod_in.nombre.strip(),
      codigo=prod_in.codigo.upper().strip(),
      precio_actual=prod_in.precio_actual,
      activo=prod_in.activo,
      unidad_medida=prod_in.unidad_medida.value,
      es_retornable=prod_in.es_retornable,
      tipo_envase_id=prod_in.tipo_envase_id if prod_in.es_retornable else None,
  )
  db.add(nuevo_producto)
  db.commit()
  db.refresh(nuevo_producto)
  return nuevo_producto


def update_producto_db(db: Session, producto: Producto):
  db.commit()
  db.refresh(producto)
  return producto