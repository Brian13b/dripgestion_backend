import logging

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.user import User, UserRole
from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)

MIN_PASSWORD_SUPERADMIN = 10


def init_superadmin(db: Session) -> None:
    password = settings.FIRST_SUPERADMIN_PASSWORD
    if not password or len(password) < MIN_PASSWORD_SUPERADMIN:
        logger.warning(
            "FIRST_SUPERADMIN_PASSWORD no está definida (o tiene menos de %s caracteres): "
            "no se crea el superadmin inicial.",
            MIN_PASSWORD_SUPERADMIN,
        )
        return

    user = (
        db.query(User)
        .filter(User.username == settings.FIRST_SUPERADMIN_USER)
        .first()
    )
    if not user:
        superadmin = User(
            username=settings.FIRST_SUPERADMIN_USER,
            hashed_password=get_password_hash(password),
            full_name="Super Administrador",
            role=UserRole.SUPERADMIN,
            tenant_id=None,
            is_active=True,
        )
        db.add(superadmin)
        db.commit()