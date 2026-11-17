from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.user import User, UserRole


def create_superadmin():
  db = SessionLocal()
  try:
    username = "gb_soluciones_digitales"
    existing = db.query(User).filter(User.username == username).first()
    if existing:
      print(f"El superadmin '{username}' ya existe.")
      return

    superadmin = User(
        username=username,
        hashed_password=get_password_hash(
            "Superadmin123!"
        ),
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