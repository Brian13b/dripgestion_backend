from app.core.config import settings
from app.core.security import get_password_hash
from app.models.user import User, UserRole
from sqlalchemy.orm import Session


def init_superadmin(db: Session) -> None:
    user = (
        db.query(User)
        .filter(User.username == settings.FIRST_SUPERADMIN_USER)
        .first()
    )
    if not user:
        superadmin = User(
            username=settings.FIRST_SUPERADMIN_USER,
            hashed_password=get_password_hash(
                settings.FIRST_SUPERADMIN_PASSWORD
            ),
            full_name="Super Administrador",
            role=UserRole.SUPERADMIN,
            tenant_id=None,
            is_active=True,
        )
        db.add(superadmin)
        db.commit()