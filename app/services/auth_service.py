from typing import Optional

from sqlalchemy.orm import Session
from datetime import timedelta
from app.models.tenant import Tenant
from app.core import security
from app.core.config import settings
from app.crud import crud_user
from app.models.user import User, UserRole
from app.schemas.user import PasswordUpdate

def _buscar_usuario_para_login(db: Session, username: str, tenant_id: Optional[int]):
  """El username es único por empresa: se busca dentro de la empresa indicada
  y, si no está, entre los superadmin (que no pertenecen a ninguna empresa)."""
  username = username.strip()
  if tenant_id:
    user = (
        db.query(User)
        .filter(User.username == username, User.tenant_id == tenant_id)
        .first()
    )
    if user:
      return user

  return (
      db.query(User)
      .filter(
          User.username == username,
          User.tenant_id.is_(None),
          User.role == UserRole.SUPERADMIN,
      )
      .first()
  )


def autenticar_usuario(db: Session, username: str, password: str, tenant_id: Optional[int] = None) -> User:
  user = _buscar_usuario_para_login(db, username, tenant_id)

  if not user or not security.verify_password(password, user.hashed_password):
    raise ValueError("Credenciales incorrectas")

  if not user.is_active:
    raise ValueError("Usuario inactivo")

  if user.role == UserRole.SUPERADMIN:
    return user

  if not tenant_id or user.tenant_id != tenant_id:
    raise ValueError("Credenciales incorrectas para esta empresa")

  tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
  if not tenant or not tenant.is_active:
    raise ValueError(
        "El acceso de esta empresa se encuentra suspendido. Contacte a soporte."
    )

  return user

def generar_token_acceso(user: User):
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = security.create_access_token(user.id, user.token_version, expires_delta=access_token_expires)
    return {
        "access_token": token,
        "token_type": "bearer",
    }

def actualizar_password(db: Session, current_user: User, password_data: PasswordUpdate):
    if not security.verify_password(password_data.current_password, current_user.hashed_password):
        raise ValueError("La contraseña actual es incorrecta")
    
    nuevo_hash = security.get_password_hash(password_data.new_password)
    
    current_user.hashed_password = nuevo_hash

    current_user.token_version += 1
    
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    
    return current_user