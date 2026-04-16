# tests/test_confluence_endpoints.py

import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
class TestConfluenceEndpoints:
    
    async def test_get_spaces_unauthorized(self, client):
        """GET /confluence/spaces без авторизации → 401"""
        response = await client.get("/confluence/spaces")
        assert response.status_code == 401
    
    async def test_get_spaces_authorized(self, auth_client):
        """GET /confluence/spaces с авторизацией"""
        response = await auth_client.get("/confluence/spaces")
        # Может быть 200 или 502 (если Confluence не настроен)
        assert response.status_code in [200, 502]
        if response.status_code == 200:
            data = response.json()
            assert data["success"] is True
            assert "data" in data
    
    async def test_get_pages_unauthorized(self, client):
        """GET /confluence/pages без авторизации → 401"""
        response = await client.get("/confluence/pages")
        assert response.status_code == 401
    
    async def test_get_pages_authorized(self, auth_client):
        """GET /confluence/pages с авторизацией"""
        response = await auth_client.get("/confluence/pages")
        assert response.status_code in [200, 502]
        if response.status_code == 200:
            data = response.json()
            assert data["success"] is True
    
    async def test_get_pages_with_space_id(self, auth_client):
        """GET /confluence/pages?space_id=xxx с авторизацией"""
        response = await auth_client.get(
            "/confluence/pages",
            params={"space_id": "test-space-id"}
        )
        assert response.status_code in [200, 404, 502]
    
    async def test_get_page_content_unauthorized(self, client):
        """GET /confluence/pages/{id}/content без авторизации → 401"""
        response = await client.get("/confluence/pages/123/content")
        assert response.status_code == 401
    
    async def test_get_page_content_authorized(self, auth_client):
        """GET /confluence/pages/{id}/content с авторизацией"""
        response = await auth_client.get("/confluence/pages/123/content")
        assert response.status_code in [200, 404, 502]
    
    async def test_get_pages_with_limit(self, auth_client):
        """GET /confluence/pages с параметром limit"""
        response = await auth_client.get(
            "/confluence/pages",
            params={"limit": 10}
        )
        assert response.status_code in [200, 502]
        if response.status_code == 200:
            data = response.json()
            assert data["meta"]["limit"] == 10