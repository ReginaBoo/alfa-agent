from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import requests
import logging

from app.core.config import settings
from app.db.models import AtlassianToken

logger = logging.getLogger(__name__)


class TokenRefreshService:
    
    @staticmethod
    def refresh_token(refresh_token: str) -> dict:
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
        
        return {
            "access_token": result["access_token"],
            "refresh_token": result.get("refresh_token"),
            "expires_in": result.get("expires_in", 3600)
        }
    
    @staticmethod
    def update_user_tokens(db: Session, user_id: int) -> bool:
        """Обновляет все токены пользователя"""
        logger.info(f"Starting token refresh for user {user_id}")
        
        tokens = db.query(AtlassianToken).filter(
            AtlassianToken.user_id == user_id
        ).all()
        
        if not tokens:
            logger.warning(f"No tokens found for user {user_id}")
            return False
        
        old_token_prefix = tokens[0].access_token[:30] if tokens[0].access_token else "None"
        old_expires = tokens[0].expires_at
        logger.info(f"Old token: {old_token_prefix}..., expires: {old_expires}")
        
        refresh_token = tokens[0].refresh_token
        
        try:
            new_tokens = TokenRefreshService.refresh_token(refresh_token)
            expires_at = datetime.utcnow() + timedelta(seconds=new_tokens["expires_in"])
            
            for token in tokens:
                token.access_token = new_tokens["access_token"]
                token.expires_at = expires_at
                if new_tokens.get("refresh_token"):
                    token.refresh_token = new_tokens["refresh_token"]
            
            db.commit()
            
            new_token_prefix = tokens[0].access_token[:30]
            logger.info(f"New token: {new_token_prefix}..., expires: {expires_at}")
            logger.info(f"Updated {len(tokens)} tokens for user {user_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to refresh token: {e}")
            return False