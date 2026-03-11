from sqlalchemy.orm import Session
from app.crud import crud_producto
from app.schemas.producto import ProductoCreate, ProductoUpdate

def crear_producto(db: Session, prod_in: ProductoCreate, tenant_id: int):
    producto_existente = crud_producto.get_producto_by_codigo(db, prod_in.codigo, tenant_id)
    if producto_existente:
        raise ValueError("Ya existe un producto con ese código")
    return crud_producto.create_producto(db, prod_in, tenant_id)

def actualizar_precio_producto(db: Session, producto_id: int, prod_in: ProductoUpdate, tenant_id: int):
    producto = crud_producto.get_producto_by_id(db, producto_id, tenant_id)
    if not producto:
        raise ValueError("Producto no encontrado")
    
    producto.precio_actual = prod_in.precio_actual
    return crud_producto.update_producto_db(db, producto)

def alternar_estado_producto(db: Session, producto_id: int, tenant_id: int):
    producto = crud_producto.get_producto_by_id(db, producto_id, tenant_id)
    if not producto:
        raise ValueError("Producto no encontrado")
    
    producto.activo = not producto.activo
    return crud_producto.update_producto_db(db, producto)