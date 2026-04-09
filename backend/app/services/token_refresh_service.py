from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import requests
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.db.models import IntegrationToken
from app.auth.models import TokenData

logger = logging.getLogger(__name__)


class TokenRefreshService:
    
    @staticmethod
    def refresh_token(refresh_token: str) -> TokenData: 
        """Обновляет access_token через Atlassian API"""
        url = "https://auth.atlassian.com/oauth/token"
        data = {
            "grant_type": "refresh_token",
            "client_id": settings.ATLASSIAN_CLIENT_ID,
            "client_secret": settings.ATLASSIAN_CLIENT_SECRET,
            "refresh_token": refresh_token
        }
        
        logger.info(f"Refreshing token with Atlassian API")
        response = requests.post(url, json=data, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        logger.info(f"Token refresh successful, expires_in: {result.get('expires_in')}")
        
        return TokenData(
            access_token=result["access_token"],
            refresh_token=result.get("refresh_token", ""),
            expires_in=result.get("expires_in", 3600),
            scope=result.get("scope", ""),
            token_type=result.get("token_type", "Bearer")
        )
    
    @staticmethod
    async def update_user_tokens_async(db: AsyncSession, user_id: int) -> bool:
        """Асинхронное обновление всех токенов пользователя"""
        
        # Асинхронный запрос
        result = await db.execute(
            select(IntegrationToken).where(
                IntegrationToken.user_id == user_id
            )
        )
        tokens = result.scalars().all()
        
        if not tokens:
            return False
        
        # Синхронный вызов API (requests) — можно оставить синхронным
        # или заменить на httpx.AsyncClient
        new_tokens = TokenRefreshService.refresh_token(tokens[0].refresh_token)
        
        expires_at = datetime.utcnow() + timedelta(seconds=new_tokens.expires_in)
        
        for token in tokens:
            token.access_token = new_tokens.access_token
            token.expires_at = expires_at
            if new_tokens.refresh_token:
                token.refresh_token = new_tokens.refresh_token
        
        await db.commit()
        return True