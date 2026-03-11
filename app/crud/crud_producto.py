from sqlalchemy.orm import Session
from app.models.producto import Producto
from app.schemas.producto import ProductoCreate, ProductoUpdate

def get_productos_by_tenant(db: Session, tenant_id: int):
    return db.query(Producto).filter(Producto.tenant_id == tenant_id).all()

def get_producto_by_codigo(db: Session, codigo: str, tenant_id: int):
    return db.query(Producto).filter(Producto.codigo == codigo, Producto.tenant_id == tenant_id).first()

def get_producto_by_id(db: Session, producto_id: int, tenant_id: int):
    return db.query(Producto).filter(Producto.id == producto_id, Producto.tenant_id == tenant_id).first()

def create_producto(db: Session, prod_in: ProductoCreate, tenant_id: int):
    nuevo_producto = Producto(
        tenant_id=tenant_id,
        nombre=prod_in.nombre,
        codigo=prod_in.codigo,
        precio_actual=prod_in.precio_actual
    )
    db.add(nuevo_producto)
    db.commit()
    db.refresh(nuevo_producto)
    return nuevo_producto

def update_producto_db(db: Session, producto: Producto):
    db.commit()
    db.refresh(producto)
    return producto