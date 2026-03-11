from sqlalchemy import Column, Integer, String, Boolean, Enum
from app.db.base import Base
import enum

class UserRole(str, enum.Enum):
    ADMIN = "admin"          # Dueño
    REPARTIDOR = "repartidor" # Empleado
    CLIENTE = "cliente"      # Usuario final

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=False) # Multitenant clave
    
    # Para login: Admin usa email/user, Cliente puede usar telefono
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    
    role = Column(Enum(UserRole), default=UserRole.CLIENTE)
    is_active = Column(Boolean, default=True)
    full_name = Column(String, nullable=True)