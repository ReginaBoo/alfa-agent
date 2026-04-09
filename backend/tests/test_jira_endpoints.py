# tests/test_jira_endpoints.py

import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
class TestJiraEndpoints:
    
    async def test_get_sites_unauthorized(self, client):  # Убрали async for
        response = await client.get("/jira/sites")
        assert response.status_code == 401
    
    async def test_get_sites_authorized(self, auth_client, test_token):
        response = await auth_client.get("/jira/sites")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Проверяем оба варианта (data или sites)
        assert "data" in data or "sites" in data
        
        sites = data.get("data") or data.get("sites")
        assert len(sites) >= 1
    
    async def test_get_projects_no_instance_name(self, auth_client):
        response = await auth_client.get("/jira/projects")
        assert response.status_code in [400, 422]
    
    async def test_get_projects_invalid_instance(self, auth_client):
        response = await auth_client.get(
            "/jira/projects",
            params={"instance_name": "nonexistent"}
        )
        assert response.status_code == 404
    
    @patch("app.endpoints.jira_endpoints.jira_client")  # Правильный патч
    async def test_get_projects_success_mock(self, mock_jira_client, auth_client, test_token):
        """GET /jira/projects с моком"""
        
        # Настраиваем мок
        mock_client = AsyncMock()
        mock_project = type('Project', (), {
            'id': '10000',
            'key': 'TEST',
            'name': 'Test Project',
            'projectTypeKey': 'software'
        })()
        mock_client.get_projects.return_value = [mock_project]
        
        # Патчим создание клиента в эндпоинте
        with patch("app.endpoints.jira_endpoints.JiraClient") as MockJiraClient:
            MockJiraClient.return_value = mock_client
            
            response = await auth_client.get(
                "/jira/projects",
                params={"instance_name": "testsite"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
    
    async def test_search_issues_unauthorized(self, client):
        response = await client.get("/jira/issues")
        assert response.status_code == 401
    
    @patch("app.endpoints.jira_endpoints.JiraClient")
    async def test_search_issues_success_mock(self, MockJiraClient, auth_client, test_token):
        """GET /jira/issues с моком"""
        
        mock_client = AsyncMock()
        mock_response = type('SearchResponse', (), {
            'issues': [],
            'total': 0
        })()
        mock_client.search_issues.return_value = mock_response
        MockJiraClient.return_value = mock_client
        
        response = await auth_client.get(
            "/jira/issues",
            params={
                "instance_name": "testsite",
                "jql": "project = TEST"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    
    async def test_sync_issues_unauthorized(self, client):
        response = await client.post("/jira/sync/TEST")
        assert response.status_code == 401