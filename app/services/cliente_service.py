from app.core import security
from app.crud import crud_cliente
from app.models.cliente import Cliente
from app.models.producto import TipoEnvase
from app.models.user import User, UserRole
from app.schemas.cliente import ClienteCreate
from sqlalchemy.orm import Session

def _enriquecer_envases_cliente(
    cliente: Cliente, mapa_envases: dict[str, TipoEnvase]
):
  detalle = []
  if isinstance(cliente.stock_envases, dict):
    for env_id_str, cant in cliente.stock_envases.items():
      cantidad = int(cant or 0)
      if cantidad <= 0:
        continue
      tipo = mapa_envases.get(str(env_id_str))
      if tipo:
        detalle.append({
            "tipo_envase_id": tipo.id,
            "nombre": tipo.nombre,
            "codigo": tipo.codigo,
            "cantidad": cantidad,
            "valor_reposicion": tipo.valor_reposicion,
            "subtotal_reposicion": round(cantidad * tipo.valor_reposicion, 2),
        })
  cliente.envases_detalle = detalle
  return cliente

def crear_cliente_con_acceso(
    db: Session, cliente_in: ClienteCreate, tenant_id: int
):
  if not cliente_in.telefono:
    raise ValueError("El teléfono es obligatorio para el acceso")

  usuario_existente = (
      db.query(User)
      .filter(
          User.username == cliente_in.telefono,
          User.tenant_id == tenant_id,
      )
      .first()
  )
  if usuario_existente:
    raise ValueError("Este teléfono ya tiene acceso al portal en esta empresa")

  nuevo_usuario = User(
      tenant_id=tenant_id,
      username=cliente_in.telefono,
      hashed_password=security.get_password_hash(cliente_in.pin_acceso),
      role=UserRole.CLIENTE,
      full_name=cliente_in.nombre_negocio,
      is_active=True,
  )
  db.add(nuevo_usuario)
  db.flush()

  cliente_db = crud_cliente.create_cliente(
      db=db,
      cliente_in=cliente_in,
      user_id=nuevo_usuario.id,
      tenant_id=tenant_id,
  )
  cliente_db.envases_detalle = []
  return cliente_db

def obtener_clientes_paginados(
    db: Session, tenant_id: int, skip: int = 0, limit: int = 100
):
  query = db.query(Cliente).filter(Cliente.tenant_id == tenant_id)
  total = query.count()
  items = query.offset(skip).limit(limit).all()

  tipos_envase = (
      db.query(TipoEnvase).filter(TipoEnvase.tenant_id == tenant_id).all()
  )
  mapa_envases = {str(e.id): e for e in tipos_envase}

  for item in items:
    _enriquecer_envases_cliente(item, mapa_envases)

  return {"total": total, "items": items}

def obtener_cliente_por_id(db: Session, cliente_id: int, tenant_id: int):
  cliente = (
      db.query(Cliente)
      .filter(Cliente.id == cliente_id, Cliente.tenant_id == tenant_id)
      .first()
  )
  if not cliente:
    raise ValueError("Cliente no encontrado")

  tipos_envase = (
      db.query(TipoEnvase).filter(TipoEnvase.tenant_id == tenant_id).all()
  )
  mapa_envases = {str(e.id): e for e in tipos_envase}
  return _enriquecer_envases_cliente(cliente, mapa_envases)


def actualizar_cliente(
    db: Session, cliente_id: int, update_data: dict, tenant_id: int
):
  cliente = (
      db.query(Cliente)
      .filter(Cliente.id == cliente_id, Cliente.tenant_id == tenant_id)
      .first()
  )
  if not cliente:
    raise ValueError("Cliente no encontrado")

  usuario = (
      db.query(User).filter(User.id == cliente.user_id).first()
      if cliente.user_id
      else None
  )

  if "telefono" in update_data and update_data["telefono"] and usuario:
    nuevo_tel = update_data["telefono"].strip()
    duplicado = (
        db.query(User)
        .filter(
            User.username == nuevo_tel,
            User.tenant_id == tenant_id,
            User.id != usuario.id,
        )
        .first()
    )
    if duplicado:
      raise ValueError("Ya existe otro cliente con ese teléfono")
    usuario.username = nuevo_tel

  if "pin_acceso" in update_data and update_data["pin_acceso"] and usuario:
    usuario.hashed_password = security.get_password_hash(
        update_data["pin_acceso"]
    )
    usuario.token_version += 1

  if "nombre_negocio" in update_data and update_data["nombre_negocio"] and usuario:
    usuario.full_name = update_data["nombre_negocio"]

  for field, value in update_data.items():
    setattr(cliente, field, value)

  db.commit()
  db.refresh(cliente)

  tipos_envase = (
      db.query(TipoEnvase).filter(TipoEnvase.tenant_id == tenant_id).all()
  )
  mapa_envases = {str(e.id): e for e in tipos_envase}
  return _enriquecer_envases_cliente(cliente, mapa_envases)


def eliminar_cliente(db: Session, cliente_id: int, tenant_id: int):
  cliente = (
      db.query(Cliente)
      .filter(Cliente.id == cliente_id, Cliente.tenant_id == tenant_id)
      .first()
  )
  if not cliente:
    raise ValueError("Cliente no encontrado")

  usuario = (
      db.query(User).filter(User.id == cliente.user_id).first()
      if cliente.user_id
      else None
  )

  db.delete(cliente)
  if usuario:
    db.delete(usuario)

  db.commit()