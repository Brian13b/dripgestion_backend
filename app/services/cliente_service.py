from sqlalchemy.orm import Session
from app.schemas.cliente import ClienteCreate
from app.models.user import User, UserRole
from app.models.cliente import Cliente
from app.core import security
from app.crud import crud_cliente

def crear_cliente_con_acceso(db: Session, cliente_in: ClienteCreate, tenant_id: int):
    if not cliente_in.telefono:
        raise ValueError("El teléfono es obligatorio para el acceso")
        
    usuario_existente = db.query(User).filter(User.username == cliente_in.telefono).first()
    if usuario_existente:
        raise ValueError("Este teléfono ya tiene acceso al portal")

    nuevo_usuario = User(
        tenant_id=tenant_id,
        username=cliente_in.telefono, 
        hashed_password=security.get_password_hash(cliente_in.pin_acceso),
        role=UserRole.CLIENTE,
        full_name=cliente_in.nombre_negocio,
        is_active=True
    )
    db.add(nuevo_usuario)
    db.flush()

    cliente_db = crud_cliente.create_cliente(
        db=db, 
        cliente_in=cliente_in, 
        user_id=nuevo_usuario.id, 
        tenant_id=tenant_id
    )
    return cliente_db

def obtener_clientes_paginados(db: Session, tenant_id: int, skip: int = 0, limit: int = 100):
    query = db.query(Cliente).filter(Cliente.tenant_id == tenant_id)
    total = query.count() 
    items = query.offset(skip).limit(limit).all()
    return {"total": total, "items": items}

def obtener_cliente_por_id(db: Session, cliente_id: int, tenant_id: int):
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id, Cliente.tenant_id == tenant_id).first()
    if not cliente:
        raise ValueError("Cliente no encontrado")
    return cliente

def actualizar_cliente(db: Session, cliente_id: int, update_data: dict, tenant_id: int):
    cliente = obtener_cliente_por_id(db, cliente_id, tenant_id)
    
    for field, value in update_data.items():
        setattr(cliente, field, value)
        
    db.commit()
    db.refresh(cliente)
    return cliente

def eliminar_cliente(db: Session, cliente_id: int, tenant_id: int):
    cliente = obtener_cliente_por_id(db, cliente_id, tenant_id)
    
    usuario = db.query(User).filter(User.id == cliente.user_id).first()
    
    db.delete(cliente)
    if usuario: 
        db.delete(usuario)
        
    db.commit()