from sqlalchemy.orm import Session
from app.models.user import User

def get_user_by_username(db: Session, username: str, tenant_id: int):
    return db.query(User).filter(User.username == username, User.tenant_id == tenant_id).first()