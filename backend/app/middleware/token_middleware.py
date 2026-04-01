# app/middleware/token_middleware.py
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.services.token_refresh_service import TokenRefreshService


class TokenRefreshMiddleware(BaseHTTPMiddleware):
    """
    Middleware для автоматического обновления токенов
    перед запросами к Jira API
    """
    
    async def dispatch(self, request: Request, call_next):
        # Проверяем, что это запрос к Jira API
        if request.url.path.startswith("/jira/"):
            # Получаем токен из параметров запроса или заголовков
            # Здесь логика получения текущего токена
            
            db = SessionLocal()
            try:
                # Пример: получаем user_id из сессии
                user_id = 1  # TODO: из сессии
                
                # Обновляем токены если нужно
                token = TokenRefreshService.get_valid_token(db, user_id)
                
                if not token:
                    raise HTTPException(status_code=401, detail="Token expired and refresh failed")
                
                # Добавляем токен в request.state для использования в endpoints
                request.state.current_token = token
                
            finally:
                db.close()
        
        response = await call_next(request)
        return response