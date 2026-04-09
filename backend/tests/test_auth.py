# tests/test_auth.py

import pytest


@pytest.mark.asyncio
class TestAuthEndpoints:
    
    async def test_login_redirect(self, client):  # Убрали async for
        response = await client.get("/auth/login", follow_redirects=False)
        assert response.status_code == 307
        assert "atlassian.com" in response.headers["location"]
    
    async def test_callback_no_code(self, client):
        response = await client.get("/auth/callback")
        assert response.status_code == 400
    
    async def test_me_unauthorized(self, client):
        response = await client.get("/auth/me")
        assert response.status_code == 401