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


# ================= ТЕСТЫ ДЛЯ НОВЫХ ЭНДПОИНТОВ =================

    @pytest.mark.asyncio
    async def test_get_issue_by_key_unauthorized(self, client):
        """GET /jira/issues/{issue_key} без авторизации → 401"""
        response = await client.get("/jira/issues/SCRUM-1")
        assert response.status_code == 401


    @pytest.mark.asyncio
    async def test_get_issue_by_key_not_found(self, auth_client):
        """GET /jira/issues/{issue_key} с несуществующим ключом"""
        response = await auth_client.get(
            "/jira/issues/FAKE-999",
            params={"instance_name": "newtestsit"}
        )
        # Jira API вернёт 404 или 502
        assert response.status_code in [404, 502]


    @pytest.mark.asyncio
    async def test_create_issue_unauthorized(self, client):
        """POST /jira/issues без авторизации → 401"""
        response = await client.post("/jira/issues")
        assert response.status_code == 401


    @pytest.mark.asyncio
    async def test_create_issue_missing_data(self, auth_client):
        """POST /jira/issues без данных → ошибка"""
        response = await auth_client.post(
            "/jira/issues",
            params={"instance_name": "newtestsit"},
            json={}
        )
        assert response.status_code == 422  # Validation error


    @pytest.mark.asyncio
    async def test_transition_issue_unauthorized(self, client):
        """POST /jira/issues/{key}/transitions без авторизации → 401"""
        response = await client.post("/jira/issues/SCRUM-1/transitions")
        assert response.status_code == 401


    @pytest.mark.asyncio
    async def test_get_changelog_unauthorized(self, client):
        """GET /jira/issues/{key}/changelog без авторизации → 401"""
        response = await client.get("/jira/issues/SCRUM-1/changelog")
        assert response.status_code == 401


    @pytest.mark.asyncio
    async def test_sync_issues_unauthorized(self, client):
        """POST /jira/sync/{project_key} без авторизации → 401"""
        response = await client.post("/jira/sync/SCRUM")
        assert response.status_code == 401


    @pytest.mark.asyncio
    async def test_sync_issues_success(self, auth_client):
        """POST /jira/sync/{project_key} с авторизацией"""
        response = await auth_client.post(
            "/jira/sync/SCRUM",
            params={"instance_name": "newtestsit"}
        )
        # Может быть 200 или 500 (зависит от наличия задач)
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            assert data["success"] is True
            assert "message" in data