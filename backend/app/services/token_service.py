# app/services/token_service.py
from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.models import IntegrationToken
from app.auth.models import TokenData, AtlassianResource


def save_tokens_for_working_sites(
    db: Session,
    user_id: int,
    atlassian_account_id: str,
    token_data: TokenData,
    working_sites: List[AtlassianResource],
    expires_at: Optional[datetime] = None
) -> List[IntegrationToken]:
    """
    Сохраняет токены для всех рабочих сайтов пользователя.
    Синхронная версия — для использования в эндпоинтах.
    """
    saved_tokens = []

    if expires_at is None:
        expires_at = datetime.utcnow() + timedelta(seconds=token_data.expires_in)

    for resource in working_sites:
        existing = db.execute(
            select(IntegrationToken).where(
                IntegrationToken.user_id == user_id,
                IntegrationToken.provider == "jira",  # или динамически, если нужно
                IntegrationToken.instance_id == resource.id
            )
        ).scalar_one_or_none()

        if existing:
            existing.access_token = token_data.access_token
            existing.refresh_token = token_data.refresh_token
            existing.expires_at = expires_at
            existing.instance_url = resource.url
            existing.instance_name = resource.name
            existing.provider_user_id = atlassian_account_id
            existing.updated_at = datetime.utcnow()
            saved_tokens.append(existing)
        else:
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


class TokenService:
    """Сервис для работы с токенами — синхронная версия"""

    def __init__(self, db: Session):
        self.db = db


    def get_valid_token(
        self,
        user_id: int,
        provider: str,
        instance_id: str
    ) -> Optional[IntegrationToken]:
        """Синхронно получает валидный токен. При необходимости обновляет."""
        token = self._fetch_token(user_id, provider, instance_id)
        if not token:
            return None

        if token.expires_at and token.expires_at <= datetime.utcnow():
            self. refresh_user_tokens(user_id)
            token = self._fetch_token(user_id, provider, instance_id)

        return token

    def _fetch_token(self, user_id: int, provider: str, instance_id: str) -> Optional[IntegrationToken]:
        """
        Ищет токен. 
        Для Atlassian-продуктов (jira/confluence) допускаем cross-provider поиск,
        так как токен доступа единый.
        """
        # 1. Сначала ищем точное совпадение
        stmt = select(IntegrationToken).where(
            IntegrationToken.user_id == user_id,
            IntegrationToken.provider == provider,
            IntegrationToken.instance_id == instance_id
        )
        token = self.db.execute(stmt).scalar_one_or_none()

        # 2. Если не нашли и это Atlassian-сервисы — пробуем провайдер "jira" как фолбэк
        if not token and provider in ("confluence", "atlassian"):
            stmt = select(IntegrationToken).where(
                IntegrationToken.user_id == user_id,
                IntegrationToken.provider == "jira",  # Фолбэк: единый токен
                IntegrationToken.instance_id == instance_id
            )
            token = self.db.execute(stmt).scalar_one_or_none()

        return token

    def refresh_user_tokens(self, user_id: int) -> bool:
        """Обновляет токены в БД и коммитит изменения"""
        from app.services.token_refresh_service import TokenRefreshService
        return TokenRefreshService.update_user_tokens(self.db, user_id)
