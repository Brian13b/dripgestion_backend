from sqlalchemy import Boolean, Column, Enum, Index, Integer, String, UniqueConstraint, text
from app.db.base import Base
import enum
from sqlalchemy.orm import validates

class UserRole(str, enum.Enum):
    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    REPARTIDOR = "repartidor"
    CLIENTE = "cliente"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            for member in cls:
                if member.value == value.lower():
                    return member
        return None

class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        # El username es único POR EMPRESA (el mismo teléfono puede ser cliente en
        # dos distribuidoras). Para el superadmin (tenant_id NULL) la unicidad
        # se garantiza con un índice parcial, porque NULL no compara igual en SQL.
        UniqueConstraint("tenant_id", "username", name="uq_users_tenant_username"),
        Index(
            "uq_users_superadmin_username",
            "username",
            unique=True,
            postgresql_where=text("tenant_id IS NULL"),
            sqlite_where=text("tenant_id IS NULL"),
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=True)
    
    username = Column(String, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    
    role = Column(
        Enum(UserRole, native_enum=False, values_callable=lambda obj: [e.value for e in obj]), 
        default=UserRole.REPARTIDOR
    )
    
    is_active = Column(Boolean, default=True)
    full_name = Column(String, nullable=True)

    token_version = Column(Integer, default=1, nullable=False)

    @validates('role')
    def validate_role(self, key, value):
        if isinstance(value, str):
            return value.lower()
        return value