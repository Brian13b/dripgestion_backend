from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.core.security import get_password_hash

db = SessionLocal()



nuevo_admin = User(
    tenant_id=2,
    username="admin@aguavida.com", 
    hashed_password=get_password_hash("1234"), 
    role=UserRole.ADMIN,
    full_name="Admin Agua Vida",
    is_active=True
)
db.add(nuevo_admin)
db.commit()