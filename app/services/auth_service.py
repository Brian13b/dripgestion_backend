from sqlalchemy.orm import Session
from datetime import timedelta
from app.core import security
from app.core.config import settings
from app.crud import crud_user

def autenticar_usuario(db: Session, username: str, password: str, tenant_id: int):
    user = crud_user.get_user_by_username(db, username=username, tenant_id=tenant_id)
    
    if not user or not security.verify_password(password, user.hashed_password):
        raise ValueError("Credenciales incorrectas para esta empresa")
        
    if not user.is_active:
        raise ValueError("Usuario inactivo")
        
    return user

def generar_token_acceso(user_id: int):
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = security.create_access_token(user_id, expires_delta=access_token_expires)
    return {
        "access_token": token,
        "token_type": "bearer",
    }