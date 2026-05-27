# tests/test_dependencies.py

import pytest
from datetime import datetime, timedelta
from fastapi import HTTPException
import secrets

from app.core.dependencies import get_current_user, get_valid_token
from app.db.models import Session as SessionModel


@pytest.mark.asyncio
class TestDependencies:
    """Тесты зависимостей (get_current_user, get_valid_token)"""
    
    async def test_get_current_user_valid(self, db_session, test_user, test_session):
        """get_current_user с валидной сессией → возвращает пользователя"""
        
        # Создаем request с cookie
        class MockRequest:
            cookies = {"session_token": test_session.session_token}
        
        request = MockRequest()
        user = get_current_user(request=request, db=db_session)
        
        assert user.id == test_user.id
        assert user.email == test_user.email
    
    async def test_get_current_user_no_cookie(self, db_session):
        """get_current_user без cookie → 401"""
        
        class MockRequest:
            cookies = {}
        
        request = MockRequest()
        
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(request=request, db=db_session)
        
        assert exc_info.value.status_code == 401
        assert "no session token" in str(exc_info.value.detail)
    
    async def test_get_current_user_expired_session(self, db_session, test_user):
        """get_current_user с истекшей сессией → 401"""
        
        # Создаем истекшую сессию
        session_token = secrets.token_urlsafe(32)
        expired_session = SessionModel(
            user_id=test_user.id,
            session_token=session_token,
            expires_at=datetime.utcnow() - timedelta(days=1),
            client_type="web"
        )
        db_session.add(expired_session)
        db_session.commit()
        
        class MockRequest:
            cookies = {"session_token": session_token}
        
        request = MockRequest()
        
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(request=request, db=db_session)
        
        assert exc_info.value.status_code == 401
        assert "Session expired" in str(exc_info.value.detail)
    
    async def test_get_valid_token_success(self, db_session, test_user, test_token):
        """get_valid_token с валидным токеном → возвращает токен"""
        
        token = get_valid_token(
            instance_name="testsite",
            current_user=test_user,
            db=db_session
        )
        
        assert token.id == test_token.id
        assert token.access_token == "test_access_token"
    
    async def test_get_valid_token_not_found(self, db_session, test_user):
        """get_valid_token с несуществующим instance_name → 404"""
        
        with pytest.raises(HTTPException) as exc_info:
            get_valid_token(
                instance_name="nonexistent",
                current_user=test_user,
                db=db_session
            )
        
        assert exc_info.value.status_code == 404