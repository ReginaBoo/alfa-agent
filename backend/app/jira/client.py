"""
Jira API Client — типизированный клиент для работы с Jira REST API v3.
"""

import httpx
from typing import List, Optional, Dict, Any
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import inspect
from app.jira.models import (
    JiraIssue,
    JiraProject,
    JiraSearchResponse,
    JiraUser,
    JiraChangelogResponse
)
from app.services.token_service import TokenService
from app.core.config import settings


class JiraClient:
    """Клиент для Jira API с автоматическим обновлением токенов"""

    def __init__(self, token_service: TokenService):
        self.token_service = token_service
        self.base_url = "https://api.atlassian.com/ex/jira"
        self.timeout = httpx.Timeout(30.0)

    async def _request(
        self,
        cloud_id: str,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Выполняет запрос к Jira API с автоматическим обновлением токена.

        Args:
            cloud_id: ID сайта Atlassian
            endpoint: Эндпоинт API (начинается с /)
            method: HTTP метод (GET, POST, PUT, DELETE)
            params: Query параметры
            json: JSON тело запроса
            user_id: ID пользователя в нашей системе

        Returns:
            Dict[str, Any]: JSON ответ от API
        """
        # Получаем валидный токен
        token = self.token_service.get_valid_token(
            user_id=user_id,
            provider="jira",  # или "confluence"
            instance_id=cloud_id
        )

        if inspect.isawaitable(token):
            token = await token

        if not token:
            raise ValueError(f"No valid token for cloud_id {cloud_id}")

        url = f"{self.base_url}/{cloud_id}{endpoint}"
        headers = {
            "Authorization": f"Bearer {token.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Первая попытка
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json
            )

            # Если токен протух — обновляем и пробуем ещё раз (максимум 1 раз)
            if response.status_code == 401:
                # Обновляем токены пользователя
                self.token_service.refresh_user_tokens(user_id)

                # Получаем новый токен
                token = self.token_service.get_valid_token(
                    user_id=user_id,
                    provider="jira",  # или "confluence"
                    instance_id=cloud_id
                )
                if inspect.isawaitable(token):
                    token = await token

                if not token:
                    raise ValueError(
                        f"Failed to refresh token for cloud_id {cloud_id}")

                # Обновляем заголовок
                headers["Authorization"] = f"Bearer {token.access_token}"

                # Повторяем запрос
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=json
                )

            # Проверяем статус
            response.raise_for_status()
            return response.json()

    async def get_projects(
        self,
        cloud_id: str,
        user_id: Optional[int] = None
    ) -> List[JiraProject]:
        """
        Получает список всех проектов в Jira.

        Args:
            cloud_id: ID сайта Atlassian
            user_id: ID пользователя в нашей системе

        Returns:
            List[JiraProject]: Список проектов
        """
        data = await self._request(
            cloud_id=cloud_id,
            endpoint="/rest/api/3/project",
            method="GET",
            user_id=user_id
        )

        return [JiraProject(**project) for project in data]

    async def get_project(
        self,
        cloud_id: str,
        project_key: str,
        user_id: Optional[int] = None
    ) -> JiraProject:
        """
        Получает информацию о конкретном проекте.

        Args:
            cloud_id: ID сайта Atlassian
            project_key: Ключ проекта (например, "PROJ")
            user_id: ID пользователя в нашей системе

        Returns:
            JiraProject: Проект
        """
        data = await self._request(
            cloud_id=cloud_id,
            endpoint=f"/rest/api/3/project/{project_key}",
            method="GET",
            user_id=user_id
        )

        return JiraProject(**data)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(httpx.HTTPStatusError)
    )
    async def search_issues(
        self,
        cloud_id: str,
        jql: str,
        fields: Optional[List[str]] = None,
        start_at: int = 0,
        max_results: int = 50,
        user_id: Optional[int] = None
    ) -> JiraSearchResponse:
        """
        Ищет задачи по JQL запросу.

        Args:
            cloud_id: ID сайта Atlassian
            jql: JQL запрос (например, "project = PROJ AND status = 'In Progress'")
            fields: Список полей для возврата
            start_at: Смещение для пагинации
            max_results: Максимум результатов за раз
            user_id: ID пользователя в нашей системе

        Returns:
            JiraSearchResponse: Результаты поиска
        """
        params = {
            "jql": jql,
            "startAt": start_at,
            "maxResults": max_results
        }

        if fields:
            params["fields"] = ",".join(fields)
        else:
            # По умолчанию запрашиваем все поля (включая Story Points)
            params["fields"] = "*all"

        data = await self._request(
            cloud_id=cloud_id,
            endpoint="/rest/api/3/search",
            method="GET",
            params=params,
            user_id=user_id
        )

        return JiraSearchResponse(**data)

    async def get_issue(
        self,
        cloud_id: str,
        issue_key: str,
        user_id: Optional[int] = None
    ) -> JiraIssue:
        """
        Получает задачу по ключу.

        Args:
            cloud_id: ID сайта Atlassian
            issue_key: Ключ задачи (например, "PROJ-123")
            user_id: ID пользователя в нашей системе

        Returns:
            JiraIssue: Задача
        """
        data = await self._request(
            cloud_id=cloud_id,
            endpoint=f"/rest/api/3/issue/{issue_key}",
            method="GET",
            user_id=user_id
        )

        return JiraIssue(**data)

    async def create_issue(
        self,
        cloud_id: str,
        project_key: str,
        summary: str,
        issue_type: str,
        description: Optional[str] = None,
        assignee_account_id: Optional[str] = None,
        priority: Optional[str] = None,
        labels: Optional[List[str]] = None,
        user_id: Optional[int] = None
    ) -> JiraIssue:
        """
        Создаёт новую задачу в Jira.

        Args:
            cloud_id: ID сайта Atlassian
            project_key: Ключ проекта
            summary: Заголовок задачи
            issue_type: Тип задачи (Task, Bug, Story и т.д.)
            description: Описание
            assignee_account_id: ID исполнителя
            priority: Приоритет
            labels: Метки
            user_id: ID пользователя в нашей системе

        Returns:
            JiraIssue: Созданная задача
        """
        payload = {
            "fields": {
                "project": {"key": project_key},
                "summary": summary,
                "issuetype": {"name": issue_type}
            }
        }

        if description:
            payload["fields"]["description"] = {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": description}
                        ]
                    }
                ]
            }

        if assignee_account_id:
            payload["fields"]["assignee"] = {"accountId": assignee_account_id}

        if priority:
            payload["fields"]["priority"] = {"name": priority}

        if labels:
            payload["fields"]["labels"] = labels

        data = await self._request(
            cloud_id=cloud_id,
            endpoint="/rest/api/3/issue",
            method="POST",
            json=payload,
            user_id=user_id
        )

        # Получаем созданную задачу полностью
        return await self.get_issue(cloud_id, data["key"], user_id)

    async def update_issue_status(
        self,
        cloud_id: str,
        issue_key: str,
        transition_id: str,
        user_id: Optional[int] = None
    ) -> None:
        """
        Обновляет статус задачи.

        Args:
            cloud_id: ID сайта Atlassian
            issue_key: Ключ задачи
            transition_id: ID перехода (статуса)
            user_id: ID пользователя в нашей системе
        """
        payload = {
            "transition": {"id": transition_id}
        }

        await self._request(
            cloud_id=cloud_id,
            endpoint=f"/rest/api/3/issue/{issue_key}/transitions",
            method="POST",
            json=payload,
            user_id=user_id
        )

    async def get_issue_changelog(
        self,
        cloud_id: str,
        issue_key: str,
        user_id: Optional[int] = None
    ) -> JiraChangelogResponse:
        """
        Получает историю изменений задачи.
        Нужно для метрики Deadline Stability.

        Args:
            cloud_id: ID сайта Atlassian
            issue_key: Ключ задачи
            user_id: ID пользователя в нашей системе

        Returns:
            JiraChangelogResponse: История изменений
        """
        data = await self._request(
            cloud_id=cloud_id,
            endpoint=f"/rest/api/3/issue/{issue_key}/changelog",
            method="GET",
            user_id=user_id
        )

        return JiraChangelogResponse(**data)

    async def get_issue_worklog(
        self,
        cloud_id: str,
        issue_key: str,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Получает журнал работ по задаче.

        Args:
            cloud_id: ID сайта Atlassian
            issue_key: Ключ задачи
            user_id: ID пользователя в нашей системе

        Returns:
            Dict: Журнал работ
        """
        return await self._request(
            cloud_id=cloud_id,
            endpoint=f"/rest/api/3/issue/{issue_key}/worklog",
            method="GET",
            user_id=user_id
        )
