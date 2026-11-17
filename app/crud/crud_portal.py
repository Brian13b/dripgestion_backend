from app.models.cliente import Cliente
from app.models.logistica import Movimiento
from app.models.producto import Producto, TipoEnvase
from sqlalchemy import desc
from sqlalchemy.orm import Session


def get_cliente_por_usuario(db: Session, user_id: int, tenant_id: int):
  return (
      db.query(Cliente)
      .filter(Cliente.user_id == user_id, Cliente.tenant_id == tenant_id)
      .first()
  )


def get_ultimos_movimientos_cliente(
    db: Session, cliente_id: int, tenant_id: int, limite: int = 10
):
  return (
      db.query(Movimiento)
      .filter(
          Movimiento.cliente_id == cliente_id,
          Movimiento.tenant_id == tenant_id,
      )
      .order_by(desc(Movimiento.fecha))
      .limit(limite)
      .all()
  )


def get_productos_tenant(db: Session, tenant_id: int):
  return db.query(Producto).filter(Producto.tenant_id == tenant_id).all()


def get_tipos_envase_tenant(db: Session, tenant_id: int):
  return db.query(TipoEnvase).filter(TipoEnvase.tenant_id == tenant_id).all()