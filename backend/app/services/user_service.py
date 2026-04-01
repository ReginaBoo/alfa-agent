# app/services/user_service.py
from sqlalchemy.orm import Session
from app.db.models import User


def get_or_create_user(db: Session, user_info: dict) -> User:
    """Получает существующего пользователя или создает нового"""
    user = db.query(User).filter(
        User.atlassian_account_id == user_info["account_id"]
    ).first()
    
    if not user:
        user = User(
            atlassian_account_id=user_info["account_id"],
            email=user_info.get("email"),
            display_name=user_info.get("display_name"),
            avatar_url=user_info.get("picture")
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    
    return user