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
    def refresh_github_token(refresh_token: str) -> dict:
        """Обновляет токен GitHub"""
        url = "https://github.com/login/oauth/access_token"
        data = {
            "grant_type": "refresh_token",
            "client_id": settings.GITHUB_CLIENT_ID,
            "client_secret": settings.GITHUB_CLIENT_SECRET,
            "refresh_token": refresh_token
        }
        
        logger.info("Refreshing GitHub token...")
        response = requests.post(
            url,
            headers={"Accept": "application/json"},
            json=data,
            timeout=10
        )
        response.raise_for_status()
        result = response.json()
        
        return {
            "access_token": result.get("access_token"),
            "refresh_token": result.get("refresh_token"),
            "expires_in": result.get("expires_in", 3600),
            "scope": result.get("scope", ""),
            "token_type": result.get("token_type", "bearer")
        }

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

    @staticmethod
    async def update_github_token_async(db: Session, user_id: int, instance_id: str) -> bool:
        """Асинхронно обновляет токен GitHub для конкретного инстанса"""
        token = db.query(IntegrationToken).filter(
            IntegrationToken.user_id == user_id,
            IntegrationToken.provider == "github",
            IntegrationToken.instance_id == instance_id
        ).first()
        
        if not token or not token.refresh_token:
            logger.warning(f"No refresh token available for GitHub user {instance_id}")
            return False
        
        try:
            new_data = TokenRefreshService.refresh_github_token(token.refresh_token)
            expires_at = datetime.utcnow() + timedelta(seconds=new_data.get("expires_in", 3600))
            
            token.access_token = new_data["access_token"]
            token.expires_at = expires_at
            if new_data.get("refresh_token"):
                token.refresh_token = new_data["refresh_token"]
            
            db.commit()
            logger.info(f"GitHub token refreshed for user {instance_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to refresh GitHub token for {instance_id}: {e}")
            db.rollback()
            return False

    @staticmethod
    async def get_token(db: Session, user_id: int, provider: str, instance_id: str) -> IntegrationToken:
        """Получает токен для конкретного провайдера и инстанса"""
        return db.query(IntegrationToken).filter(
            IntegrationToken.user_id == user_id,
            IntegrationToken.provider == provider,
            IntegrationToken.instance_id == instance_id
        ).first()
    

    @staticmethod
    async def update_user_tokens_async(db: Session, user_id: int) -> bool:
        """Асинхронно обновляет все токены пользователя"""
        stmt = select(IntegrationToken).where(IntegrationToken.user_id == user_id)
        tokens = db.execute(stmt).scalars().all()
        
        if not tokens:
            return False
        
        # Используем синхронный метод для обновления
        # В асинхронном контексте это нормально для коротких операций
        new_data = TokenRefreshService.refresh_token(tokens[0].refresh_token)
        expires_at = datetime.utcnow() + timedelta(seconds=new_data.expires_in)
        
        for token in tokens:
            token.access_token = new_data.access_token
            token.expires_at = expires_at
            if new_data.refresh_token:
                token.refresh_token = new_data.refresh_token
        
        db.commit()
        logger.info(f"Tokens refreshed async for user {user_id}")
        return True