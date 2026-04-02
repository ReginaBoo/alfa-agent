# app/core/dependencies.py
from datetime import datetime
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session as DbSession

from app.db.session import get_db
from app.db.models import User, AtlassianToken, Session as SessionModel
from app.services.token_refresh_service import TokenRefreshService


def get_current_user(request: Request, db: DbSession = Depends(get_db)) -> User:
    """
    Получает текущего пользователя по сессии из cookie.
    Session token передаётся в куках: session_token=...
    """
    session_token = request.cookies.get("session_token")
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated: no session token")
    
    session = db.query(SessionModel).filter(
        SessionModel.session_token == session_token,
        SessionModel.expires_at > datetime.utcnow()
    ).first()
    
    if not session:
        raise HTTPException(status_code=401, detail="Session expired or invalid")

    return session.user


def get_valid_token(
    site_name: str = None,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db)
) -> AtlassianToken:
    """
    Получает валидный токен для указанного сайта.
    Если токен истек, автоматически обновляет.
    """
    query = db.query(AtlassianToken).filter(
        AtlassianToken.user_id == current_user.id
    )
    
    if site_name:
        query = query.filter(AtlassianToken.site_name == site_name)
    
    token = query.first()
    
    if not token:
        raise HTTPException(
            status_code=404,
            detail=f"No token found for site '{site_name}'"
        )
    
    # Проверяем, не истек ли токен
    if token.expires_at and token.expires_at <= datetime.utcnow():
        print(f"Token expired at {token.expires_at}, refreshing...")
        TokenRefreshService.update_user_tokens(db, current_user.id)
        db.refresh(token)
        print(f"Token refreshed, new expires: {token.expires_at}")
    
    return token


def get_valid_token_by_cloud_id(
    cloud_id: str,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db)
) -> AtlassianToken:
    """
    Получает валидный токен по cloud_id (для Confluence, Bitbucket)
    """
    token = db.query(AtlassianToken).filter(
        AtlassianToken.user_id == current_user.id,
        AtlassianToken.cloud_id == cloud_id
    ).first()
    
    if not token:
        raise HTTPException(
            status_code=404,
            detail=f"No token found for cloud_id '{cloud_id}'"
        )
    
    # Проверяем, не истек ли токен
    if token.expires_at and token.expires_at <= datetime.utcnow():
        TokenRefreshService.update_user_tokens(db, current_user.id)
        db.refresh(token)
    
    return token