# app/services/token_refresh_service.py
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select
import requests
import logging

from app.core.config import settings
from app.db.models import IntegrationToken
from app.auth.models import TokenData

logger = logging.getLogger(__name__)

class TokenRefreshService:
    @staticmethod
    def refresh_token(refresh_token: str) -> TokenData:
        url = "https://auth.atlassian.com/oauth/token"
        data = {
            "grant_type": "refresh_token",
            "client_id": settings.ATLASSIAN_CLIENT_ID,
            "client_secret": settings.ATLASSIAN_CLIENT_SECRET,
            "refresh_token": refresh_token
        }
        
        logger.info("Refreshing Atlassian token...")
        response = requests.post(url, json=data, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        return TokenData(
            access_token=result["access_token"],
            refresh_token=result.get("refresh_token", ""),
            expires_in=result.get("expires_in", 3600),
            scope=result.get("scope", ""),
            token_type=result.get("token_type", "Bearer")
        )

    @staticmethod
    def update_user_tokens(db: Session, user_id: int) -> bool:
        """Синхронно обновляет все токены пользователя и делает commit"""
        stmt = select(IntegrationToken).where(IntegrationToken.user_id == user_id)
        tokens = db.execute(stmt).scalars().all()
        
        if not tokens:
            return False
        
        new_data = TokenRefreshService.refresh_token(tokens[0].refresh_token)
        expires_at = datetime.utcnow() + timedelta(seconds=new_data.expires_in)
        
        for token in tokens:
            token.access_token = new_data.access_token
            token.expires_at = expires_at
            if new_data.refresh_token:
                token.refresh_token = new_data.refresh_token
        
        db.commit()
        logger.info(f"Tokens refreshed for user {user_id}")
        return True