# app/services/token_service.py
from app.db.models import IntegrationToken
from app.auth.models import TokenData, AtlassianResource
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session


def save_tokens_for_working_sites(
    db: Session,
    user_id: int,
    atlassian_account_id: str,
    token_data: TokenData,
    working_sites: list[AtlassianResource],
    expires_at: Optional[datetime] = None
) -> list[IntegrationToken]:
    """
    Сохраняет токены для всех рабочих сайтов пользователя.
    """
    saved_tokens = []
    
    if expires_at is None:
        expires_at = datetime.utcnow() + timedelta(seconds=token_data.expires_in)
    
    for resource in working_sites:
        # Проверяем существующую запись
        existing = db.query(IntegrationToken).filter(
            IntegrationToken.user_id == user_id,
            IntegrationToken.provider == "jira",
            IntegrationToken.instance_id == resource.id
        ).first()
        
        if existing:
            # Обновляем существующую запись
            existing.access_token = token_data.access_token
            existing.refresh_token = token_data.refresh_token
            existing.expires_at = expires_at
            existing.instance_url = resource.url
            existing.instance_name = resource.name
            existing.provider_user_id = atlassian_account_id
            existing.updated_at = datetime.utcnow()
            saved_tokens.append(existing)
        else:
            # Создаём новую запись
            new_token = IntegrationToken(
                user_id=user_id,
                provider="jira",
                provider_user_id=atlassian_account_id,
                instance_id=resource.id,
                instance_name=resource.name,
                instance_url=resource.url,
                access_token=token_data.access_token,
                refresh_token=token_data.refresh_token,
                expires_at=expires_at
            )
            db.add(new_token)
            saved_tokens.append(new_token)
    
    db.commit()
    
    for token in saved_tokens:
        db.refresh(token)
    
    return saved_tokens