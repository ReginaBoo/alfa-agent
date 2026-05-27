# tests/test_jira_client.py

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.jira.client import JiraClient
from app.services.token_service import TokenService


class TestJiraClient:
    """Тесты для JiraClient"""
    
    @pytest.fixture
    def mock_token_service(self):
        """Мок TokenService"""
        service = MagicMock(spec=TokenService)
        service.get_valid_token = AsyncMock(return_value=MagicMock(
            access_token="test_token",
            refresh_token="test_refresh"
        ))
        service.refresh_user_tokens = AsyncMock(return_value=True)
        return service
    
    @pytest.fixture
    def jira_client(self, mock_token_service):
        """Создает JiraClient с моком"""
        return JiraClient(mock_token_service)
    
    @pytest.mark.asyncio
    async def test_get_projects_success(self, jira_client, mock_token_service):
        """Тест: успешное получение проектов"""
        
        # Мокаем HTTP запрос
        with patch("httpx.AsyncClient.request") as mock_request:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = [
                {"id": "10000", "key": "TEST", "name": "Test Project"}
            ]
            mock_request.return_value = mock_response
            
            projects = await jira_client.get_projects(
                cloud_id="test-cloud",
                user_id=1
            )
            
            assert len(projects) == 1
            assert projects[0].key == "TEST"
            
            # Проверяем, что токен запрашивался
            mock_token_service.get_valid_token.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_projects_token_expired(self, jira_client, mock_token_service):
        """Тест: токен протух, обновляем и повторяем"""
        
        # Первый запрос возвращает 401
        with patch("httpx.AsyncClient.request") as mock_request:
            mock_response_401 = MagicMock()
            mock_response_401.status_code = 401
            
            mock_response_200 = MagicMock()
            mock_response_200.status_code = 200
            mock_response_200.json.return_value = [
                {"id": "10000", "key": "TEST", "name": "Test Project"}
            ]
            
            # Первый вызов → 401, второй → 200
            mock_request.side_effect = [mock_response_401, mock_response_200]
            
            projects = await jira_client.get_projects(
                cloud_id="test-cloud",
                user_id=1
            )
            
            # Проверяем, что refresh вызывался
            mock_token_service.refresh_user_tokens.assert_called_once()
            assert len(projects) == 1
    
    @pytest.mark.asyncio
    async def test_search_issues_with_story_points(self, jira_client, mock_token_service):
        """Тест: поиск задач с Story Points"""
        
        with patch("httpx.AsyncClient.request") as mock_request:
            mock_response = MagicMock()
            mock_response.status_code = 200
            # Исправленный мок с правильными полями
            mock_response.json.return_value = {
                "expand": "schema,names",
                "startAt": 0,
                "maxResults": 50,
                "total": 1,
                "issues": [
                    {
                        "id": "10001",  # 👈 Добавили id
                        "key": "TEST-1",
                        "fields": {
                            "summary": "Test issue",
                            "customfield_10016": 5,
                            "status": {
                                "name": "In Progress",
                                "id": "3"  # 👈 Добавили id
                            },
                            "issuetype": {  # 👈 Добавили issuetype
                                "name": "Story",
                                "id": "10001"
                            },
                            "created": "2024-01-01T10:00:00.000+0000",  # 👈 Добавили
                            "updated": "2024-01-15T15:30:00.000+0000"   # 👈 Добавили
                        }
                    }
                ]
            }
            mock_request.return_value = mock_response
            
            result = await jira_client.search_issues(
                cloud_id="test-cloud",
                jql="project = TEST",
                user_id=1
            )
            
            assert result.total == 1
            
            # Проверяем, что fields передан
            call_kwargs = mock_request.call_args[1]
            assert "params" in call_kwargs
            params = call_kwargs["params"]
            assert params["jql"] == "project = TEST"
            assert params["maxResults"] == 50