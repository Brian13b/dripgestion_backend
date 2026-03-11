from sqlalchemy.orm import Session
from app.schemas.cliente import ClienteCreate
from app.models.user import User, UserRole
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