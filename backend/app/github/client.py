"""
GitHub API клиент с поддержкой автообновления токенов.
"""
import logging
import httpx
from typing import Optional, List, Dict
from datetime import datetime
from fastapi import HTTPException
from app.services.token_refresh_service import TokenRefreshService

from app.github.models import (
    GitHubIssue, GitHubRepo, GitHubUser, 
    GitHubIssueEvent, GitHubComment,
    GitHubPullRequest, GitHubPullRequestReview, GitHubCheckRun
)
from app.db.models import IntegrationToken

logger = logging.getLogger(__name__)


class GitHubClient:
    """Клиент для работы с GitHub API"""
    
    BASE_URL = "https://api.github.com"
    
    def __init__(
        self, 
        access_token: str,
        instance_id: str = None,
        instance_name: str = None
    ):
        self.access_token = access_token
        self.instance_id = instance_id  # username/org для GitHub
        self.instance_name = instance_name
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Alpha-Agent"
        }
    
    async def _make_request(
        self, 
        path: str, 
        method: str = "GET",
        params: dict = None,
        json_data: dict = None,
        db = None,
        user_id: int = None
    ) -> dict | list:
        """
        Делает асинхронный запрос к GitHub API.
        При 401 пытается обновить токен.
        """
        from app.services.token_refresh_service import TokenRefreshService
        from fastapi import HTTPException  # Добавить импорт
        
        url = f"{self.BASE_URL}/{path}"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            for attempt in range(2):
                response = await client.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    params=params,
                    json=json_data
                )
                
                if response.status_code == 401 and attempt == 0:
                    # Проверяем, можем ли обновить токен
                    if db is None or user_id is None or self.instance_id is None:
                        raise HTTPException(
                            status_code=401, 
                            detail="Token expired and cannot refresh (missing db/user_id/instance_id)"
                        )
                    
                    # Обновляем токен
                    refresh_success = await TokenRefreshService.update_github_token_async(
                        db, user_id, self.instance_id
                    )
                    
                    if not refresh_success:
                        raise HTTPException(status_code=401, detail="Token refresh failed")
                    
                    # Получаем обновлённый токен из БД
                    token = await TokenRefreshService.get_token(db, user_id, "github", self.instance_id)
                    if token and token.access_token:
                        self.access_token = token.access_token
                        self.headers["Authorization"] = f"Bearer {token.access_token}"
                        continue
                    else:
                        raise HTTPException(status_code=401, detail="No token found after refresh")
                
                response.raise_for_status()
                
                if response.content:
                    return response.json()
                return {}
            
            raise Exception("Token refresh failed after retry")
    
    async def get_user(self) -> GitHubUser:
        """Получает информацию о текущем пользователе"""
        data = await self._make_request("user")
        return GitHubUser(**data)
    
    async def get_user_emails(self) -> List[Dict]:
        """Получает email пользователя"""
        return await self._make_request("user/emails")
    
    async def get_repos(
        self, 
        affiliation: str = "owner,collaborator,organization_member",
        per_page: int = 100
    ) -> List[GitHubRepo]:
        """Получает список репозиториев пользователя"""
        params = {
            "affiliation": affiliation,
            "per_page": per_page,
            "type": "all"
        }
        data = await self._make_request("user/repos", params=params)
        return [GitHubRepo(**repo) for repo in data]
    
    async def get_issues(
        self,
        owner: str,
        repo: str,
        state: str = "all",
        per_page: int = 100,
        page: int = 1
    ) -> List[GitHubIssue]:
        """Получает issues из репозитория"""
        params = {
            "state": state,
            "per_page": per_page,
            "page": page
        }
        path = f"repos/{owner}/{repo}/issues"
        data = await self._make_request(path, params=params)
        return [GitHubIssue(**issue) for issue in data if "pull_request" not in issue]
    
    async def get_issue(self, owner: str, repo: str, issue_number: int) -> GitHubIssue:
        """Получает конкретный issue"""
        path = f"repos/{owner}/{repo}/issues/{issue_number}"
        data = await self._make_request(path)
        return GitHubIssue(**data)
    
    async def get_issue_events(
        self, 
        owner: str, 
        repo: str, 
        issue_number: int
    ) -> List[GitHubIssueEvent]:
        """Получает события (events) для issue"""
        path = f"repos/{owner}/{repo}/issues/{issue_number}/events"
        data = await self._make_request(path)
        return [GitHubIssueEvent(**event) for event in data]
    
    async def get_issue_timeline(
        self, 
        owner: str, 
        repo: str, 
        issue_number: int
    ) -> List[dict]:
        """Получает детальную временную шкалу issue"""
        path = f"repos/{owner}/{repo}/issues/{issue_number}/timeline"
        return await self._make_request(path)
    
    async def get_comments(
        self, 
        owner: str, 
        repo: str, 
        issue_number: int
    ) -> List[GitHubComment]:
        """Получает комментарии к issue"""
        path = f"repos/{owner}/{repo}/issues/{issue_number}/comments"
        data = await self._make_request(path)
        return [GitHubComment(**comment) for comment in data]
    
    async def create_issue(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str = None,
        assignee: str = None,
        labels: List[str] = None,
        milestone: int = None
    ) -> GitHubIssue:
        """Создаёт новый issue"""
        payload = {"title": title}
        if body:
            payload["body"] = body
        if assignee:
            payload["assignee"] = assignee
        if labels:
            payload["labels"] = labels
        if milestone:
            payload["milestone"] = milestone
        
        path = f"repos/{owner}/{repo}/issues"
        data = await self._make_request(path, method="POST", json_data=payload)
        return GitHubIssue(**data)
    
    async def update_issue(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        state: str = None,
        title: str = None,
        body: str = None,
        assignee: str = None,
        labels: List[str] = None,
        milestone: int = None
    ) -> GitHubIssue:
        """Обновляет существующий issue"""
        payload = {}
        if state:
            payload["state"] = state
        if title:
            payload["title"] = title
        if body:
            payload["body"] = body
        if assignee:
            payload["assignee"] = assignee
        if labels:
            payload["labels"] = labels
        if milestone:
            payload["milestone"] = milestone
        
        path = f"repos/{owner}/{repo}/issues/{issue_number}"
        data = await self._make_request(path, method="PATCH", json_data=payload)
        return GitHubIssue(**data)
    
    async def add_comment(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        body: str
    ) -> GitHubComment:
        """Добавляет комментарий к issue"""
        payload = {"body": body}
        path = f"repos/{owner}/{repo}/issues/{issue_number}/comments"
        data = await self._make_request(path, method="POST", json_data=payload)
        return GitHubComment(**data)

    # ================= PULL REQUESTS =================

    async def get_pull_requests(
        self,
        owner: str,
        repo: str,
        state: str = "all",
        per_page: int = 100,
        page: int = 1
    ) -> List[GitHubPullRequest]:
        """Получает список Pull Requests"""
        params = {
            "state": state,
            "per_page": per_page,
            "page": page
        }
        path = f"repos/{owner}/{repo}/pulls"
        data = await self._make_request(path, params=params)
        return [GitHubPullRequest(**pr) for pr in data]

    async def get_pull_request(
        self,
        owner: str,
        repo: str,
        pr_number: int
    ) -> GitHubPullRequest:
        """Получает конкретный Pull Request"""
        path = f"repos/{owner}/{repo}/pulls/{pr_number}"
        data = await self._make_request(path)
        return GitHubPullRequest(**data)

    async def get_pull_request_reviews(
        self,
        owner: str,
        repo: str,
        pr_number: int
    ) -> List[GitHubPullRequestReview]:
        """Получает ревью для Pull Request"""
        path = f"repos/{owner}/{repo}/pulls/{pr_number}/reviews"
        data = await self._make_request(path)
        return [GitHubPullRequestReview(**review) for review in data]

    async def get_pull_request_commits(
        self,
        owner: str,
        repo: str,
        pr_number: int
    ) -> List[dict]:
        """Получает коммиты внутри Pull Request"""
        path = f"repos/{owner}/{repo}/pulls/{pr_number}/commits"
        return await self._make_request(path)

    # ================= COMMITS =================

    async def get_commits(
        self,
        owner: str,
        repo: str,
        per_page: int = 100,
        page: int = 1,
        since: str = None,
        until: str = None
    ) -> List[dict]:
        """
        Получает список коммитов с полной информацией.
        Возвращает raw dict для детальной обработки.
        """
        params = {
            "per_page": per_page,
            "page": page
        }
        if since:
            params["since"] = since
        if until:
            params["until"] = until
        
        path = f"repos/{owner}/{repo}/commits"
        return await self._make_request(path, params=params)

    async def get_commit(
        self,
        owner: str,
        repo: str,
        sha: str
    ) -> dict:
        """Получает детальные данные коммита (включая additions/deletions)"""
        path = f"repos/{owner}/{repo}/commits/{sha}"
        return await self._make_request(path)

    # ================= CHECK RUNS (CI/CD) =================

    async def get_check_runs(
        self,
        owner: str,
        repo: str,
        sha: str
    ) -> List[GitHubCheckRun]:
        """Получает Check Runs для конкретного коммита"""
        path = f"repos/{owner}/{repo}/commits/{sha}/check-runs"
        data = await self._make_request(path)
        checks = data.get("check_runs", [])
        return [GitHubCheckRun(**check) for check in checks]

    async def get_check_suite(
        self,
        owner: str,
        repo: str,
        sha: str
    ) -> dict:
        """Получает Check Suite для коммита (агрегированные статусы)"""
        path = f"repos/{owner}/{repo}/commits/{sha}/check-suites"
        return await self._make_request(path)
