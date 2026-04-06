# app/services/token_service.py
from app.db.models import AtlassianToken
from app.auth.models import TokenData, AtlassianResource
from datetime import datetime, timedelta
from typing import Optional


def save_tokens_for_working_sites(
    db,
    user_id: int,
    atlassian_account_id: str,
    token_data: TokenData,
    working_sites: list[AtlassianResource],
    expires_at: Optional[datetime] = None
) -> list[AtlassianToken]:
    """
    Сохраняет токены для всех рабочих сайтов пользователя.
    Возвращает список сохранённых записей AtlassianToken.
    """
    saved_tokens = []
    
    if expires_at is None:
        expires_at = datetime.utcnow() + timedelta(seconds=token_data.expires_in)
    
    for resource in working_sites:
        # Проверяем, есть ли уже запись для этого сайта
        existing = db.query(AtlassianToken).filter_by(
            user_id=user_id,
            cloud_id=resource.id
        ).first()
        
        if existing:
            # Обновляем существующую запись
            existing.access_token = token_data.access_token
            existing.refresh_token = token_data.refresh_token
            existing.expires_at = expires_at
            existing.site_url = resource.url
            existing.site_name = resource.name
            existing.atlassian_account_id = atlassian_account_id
            saved_tokens.append(existing)
        else:
            # Создаём новую запись
            new_token = AtlassianToken(
                user_id=user_id,
                atlassian_account_id=atlassian_account_id,
                cloud_id=resource.id,
                site_url=resource.url,
                site_name=resource.name,
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