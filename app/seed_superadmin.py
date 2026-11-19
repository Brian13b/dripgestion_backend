"""Crea el superadmin inicial a mano.

Uso (PowerShell):
    $env:FIRST_SUPERADMIN_PASSWORD = "una-clave-larga-y-privada"
    python -m app.seed_superadmin

La contraseña NUNCA va escrita en el código: se toma de FIRST_SUPERADMIN_PASSWORD.
"""
from app.core.config import settings
from app.db.init_db import MIN_PASSWORD_SUPERADMIN
from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.user import User, UserRole


def create_superadmin():
  password = settings.FIRST_SUPERADMIN_PASSWORD
  if not password or len(password) < MIN_PASSWORD_SUPERADMIN:
    print(
        "Definí FIRST_SUPERADMIN_PASSWORD (mínimo "
        f"{MIN_PASSWORD_SUPERADMIN} caracteres) antes de correr este script."
    )
    return

  db = SessionLocal()
  try:
    username = settings.FIRST_SUPERADMIN_USER
    existing = db.query(User).filter(User.username == username).first()
    if existing:
      print(f"El superadmin '{username}' ya existe.")
      return

    superadmin = User(
        username=username,
        hashed_password=get_password_hash(password),
        full_name="GB Soluciones Digitales",
        role=UserRole.SUPERADMIN,
        tenant_id=None,
        is_active=True,
    )
    db.add(superadmin)
    db.commit()
    print(f"Superadmin '{username}' creado con éxito.")
  finally:
    db.close()


if __name__ == "__main__":
  create_superadmin()
