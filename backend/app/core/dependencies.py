# app/core/dependencies.py
from datetime import datetime
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session as DbSession
from sqlalchemy import select

from app.db.session import get_db
from app.db.models import User, IntegrationToken, Session as SessionModel
from app.services.token_refresh_service import TokenRefreshService


from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session as DbSession, joinedload

from app.db.session import get_db
from app.db.models import User, Session as SessionModel


from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session as DbSession, joinedload

from app.db.session import get_db
from app.db.models import User, Session as SessionModel


def get_current_user(request: Request, db: DbSession = Depends(get_db)) -> User:
    # Сначала пробуем получить токен из заголовка X-Session-Token (Electron/веб)
    session_token = request.headers.get("X-Session-Token")
    
    # Если нет в заголовке, пробуем из cookie
    if not session_token:
        session_token = request.cookies.get("session_token")
        if session_token:
            print(f"✅ Using token from cookie")
    
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated: no session token")
    
    print(f"🔍 Looking for token: {session_token[:20]}...")
    
    # Ищем сессию
    session = db.query(SessionModel).options(
        joinedload(SessionModel.user)
    ).filter(
        SessionModel.session_token == session_token,
        SessionModel.expires_at > datetime.utcnow()
    ).first()
    
    if not session:
        print(f"❌ Session not found or expired for token: {session_token[:20]}...")
        raise HTTPException(status_code=401, detail="Session expired or invalid")

    if not session.user:
        raise HTTPException(status_code=401, detail="User not found for session")
    
    # Продлеваем сессию
    session.expires_at = datetime.utcnow() + timedelta(days=7)
    db.commit()
    
    return session.user


def get_valid_token(
    instance_name: str = None,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db)
) -> IntegrationToken:
    """
    Получает валидный токен для указанного сайта (по instance_name).
    Если токен истек, автоматически обновляет.
    """
    from app.db.models import IntegrationToken
    from app.services.token_refresh_service import TokenRefreshService
    
    query = db.query(IntegrationToken).filter(
        IntegrationToken.user_id == current_user.id,
        IntegrationToken.provider == "jira"
    )
    
    if instance_name:
        query = query.filter(IntegrationToken.instance_name == instance_name)
    
    token = query.first()
    
    if not token:
        raise HTTPException(
            status_code=404,
            detail=f"No token found for site '{instance_name}'"
        )
    
    # Проверяем, не истек ли токен
    if token.expires_at and token.expires_at <= datetime.utcnow():
        TokenRefreshService.update_user_tokens(db, current_user.id)
        db.refresh(token)
    
    return token


def get_valid_token_by_instance_id(
    instance_id: str,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db)
) -> IntegrationToken:
    """
    Получает валидный токен по instance_id (cloud_id для Jira).
    """
    from app.db.models import IntegrationToken
    from app.services.token_refresh_service import TokenRefreshService
    
    token = db.query(IntegrationToken).filter(
        IntegrationToken.user_id == current_user.id,
        IntegrationToken.instance_id == instance_id,
        IntegrationToken.provider == "jira"
    ).first()
    
    if not token:
        raise HTTPException(
            status_code=404,
            detail=f"No token found for instance_id '{instance_id}'"
        )
    
    # Проверяем, не истек ли токен
    if token.expires_at and token.expires_at <= datetime.utcnow():
        TokenRefreshService.update_user_tokens(db, current_user.id)
        db.refresh(token)
    
    return token

