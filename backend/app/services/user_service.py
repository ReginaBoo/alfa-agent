# app/services/user_service.py
from sqlalchemy.orm import Session
from app.db.models import User
from app.auth.models import UserInfo


def get_or_create_user(db: Session, user_info: UserInfo) -> User:
    """Получает существующего пользователя или создает нового"""
    # Ищем по email (уникальное поле)
    user = db.query(User).filter(User.email == user_info.email).first()
    
    if not user:
        # Создаём нового пользователя (без atlassian_account_id)
        user = User(
            email=user_info.email,
            display_name=user_info.display_name,
            avatar_url=user_info.picture
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    
    return user