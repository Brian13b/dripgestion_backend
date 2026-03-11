from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models.cliente import Cliente
from app.models.logistica import Movimiento
from app.models.producto import Producto

def get_cliente_por_usuario(db: Session, user_id: int):
    return db.query(Cliente).filter(Cliente.user_id == user_id).first()

def get_ultimos_movimientos_cliente(db: Session, cliente_id: int, limite: int = 10):
    return db.query(Movimiento).filter(
        Movimiento.cliente_id == cliente_id
    ).order_by(desc(Movimiento.fecha)).limit(limite).all()

def get_productos_tenant(db: Session, tenant_id: int):
    return db.query(Producto).filter(Producto.tenant_id == tenant_id).all()