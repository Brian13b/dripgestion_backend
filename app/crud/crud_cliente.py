from sqlalchemy.orm import Session
from app.models.cliente import Cliente
from app.schemas.cliente import ClienteCreate

def get_cliente_by_id(db: Session, cliente_id: int, tenant_id: int):
    return db.query(Cliente).filter(
        Cliente.id == cliente_id,
        Cliente.tenant_id == tenant_id
    ).first()

def create_cliente(db: Session, cliente_in: ClienteCreate, user_id: int, tenant_id: int):
    cliente_db = Cliente(
        **cliente_in.model_dump(),
        tenant_id=tenant_id,
        user_id=user_id,
        saldo_dinero=0.0,
        stock_envases={}
    )
    db.add(cliente_db)
    db.commit()
    db.refresh(cliente_db)
    return cliente_db