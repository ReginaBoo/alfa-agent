"""
Сервис для синхронизации Issues из GitHub в БД.
"""
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_
import json

from app.db.models import IntegrationToken, RawEvent
from app.db.models.normalized import GithubIssue, GithubIssueEvent
from app.services.github_project_link_service import get_project_by_repo

logger = logging.getLogger(__name__)


class GithubSyncService:
    """Синхронизация данных из GitHub Issues в БД"""

    def __init__(self, db: Session):
        self.db = db

    def _get_github_token(self, user_id: int, instance_id: str) -> IntegrationToken:
        """Получает токен GitHub для пользователя и инстанса"""
        token = self.db.query(IntegrationToken).filter(
            IntegrationToken.user_id == user_id,
            IntegrationToken.instance_id == instance_id,
            IntegrationToken.provider == "github"
        ).first()

        if not token:
            raise ValueError(f"Token not found for GitHub user {instance_id}")
        
        return token
    

    async def sync_repo_issues_async(
        self,
        user_id: int,
        instance_id: str,
        repo_full_name: str
    ) -> dict:
        """Асинхронная синхронизация issues"""

        from app.github.client import GitHubClient
        from app.services.github_project_link_service import get_project_by_repo  # 👈 ДОБАВИТЬ ИМПОРТ
        
        token = self._get_github_token(user_id, instance_id)
        client = GitHubClient(
            access_token=token.access_token,
            instance_id=instance_id
        )
        
        # Разбираем owner/repo
        parts = repo_full_name.split("/")
        if len(parts) != 2:
            raise ValueError(f"Invalid repo_full_name: {repo_full_name}")
        owner, repo = parts
        
        # 👇 НАХОДИМ ПРОЕКТ
        project = get_project_by_repo(self.db, repo_full_name)
        project_id = project.id if project else None
        
        # Получаем все issues
        all_issues = []
        page = 1
        per_page = 100
        
        while True:
            issues = await client.get_issues(
                owner=owner,
                repo=repo,
                state="all",
                per_page=per_page,
                page=page
            )
            
            if not issues:
                break
            
            all_issues.extend(issues)
            
            if len(issues) < per_page:
                break
            
            page += 1
            logger.info(f"Fetching page {page} for {repo_full_name}")
        
        created_count = 0
        updated_count = 0
        
        for issue in all_issues:
            # 1. СОХРАНЯЕМ СЫРЫЕ ДАННЫЕ
            raw_event = RawEvent(
                source="github",
                event_type="issue",
                external_id=str(issue.id),
                project_integration_id=None,
                payload=issue.model_dump() if hasattr(issue, 'model_dump') else issue.dict(),
                timestamp=datetime.utcnow()
            )
            self.db.add(raw_event)
            
            # 2. СОХРАНЯЕМ/ОБНОВЛЯЕМ НОРМАЛИЗОВАННУЮ ЗАДАЧУ
            existing = self.db.query(GithubIssue).filter(
                GithubIssue.issue_id == issue.id
            ).first()
            
            # Парсим labels (убрано дублирование)
            labels_json = [label.name for label in issue.labels] if issue.labels else None
            
            # Получаем assignee
            assignee_login = None
            assignee_id = None
            if issue.assignees:
                assignee = issue.assignees[0]
                assignee_login = assignee.login
                assignee_id = assignee.id
            
            # Получаем milestone
            milestone_id = None
            milestone_title = None
            if issue.milestone:
                milestone_id = issue.milestone.id
                milestone_title = issue.milestone.title
            
            # Парсим даты
            created_at = None
            updated_at = None
            closed_at = None
            
            if issue.created_at:
                try:
                    created_at = datetime.fromisoformat(issue.created_at.replace('Z', '+00:00'))
                except:
                    created_at = datetime.utcnow()
            
            if issue.updated_at:
                try:
                    updated_at = datetime.fromisoformat(issue.updated_at.replace('Z', '+00:00'))
                except:
                    updated_at = datetime.utcnow()
            
            if issue.closed_at:
                try:
                    closed_at = datetime.fromisoformat(issue.closed_at.replace('Z', '+00:00'))
                except:
                    closed_at = None
            
            if existing:
                # Обновляем существующую задачу
                existing.title = issue.title
                existing.body = issue.body
                existing.state = issue.state
                existing.locked = issue.locked
                existing.labels = labels_json
                existing.milestone_id = milestone_id
                existing.milestone_title = milestone_title
                existing.comments_count = issue.comments
                existing.assignee_login = assignee_login
                existing.assignee_id = assignee_id
                existing.updated_at = updated_at
                existing.closed_at = closed_at
                existing.project_id = project_id  # 👈 ДОБАВЛЕНО
                existing.last_synced_at = datetime.utcnow()
                existing.snapshot_version = (existing.snapshot_version or 0) + 1
                
                updated_count += 1
            else:
                # Создаём новую задачу
                new_issue = GithubIssue(
                    issue_id=issue.id,
                    issue_number=issue.number,
                    repo_full_name=repo_full_name,
                    repo_id=issue.id,
                    title=issue.title,
                    body=issue.body,
                    state=issue.state,
                    locked=issue.locked,
                    author_login=issue.user.login if issue.user else None,
                    author_id=issue.user.id if issue.user else None,
                    assignee_login=assignee_login,
                    assignee_id=assignee_id,
                    labels=labels_json,
                    milestone_id=milestone_id,
                    milestone_title=milestone_title,
                    comments_count=issue.comments,
                    created_at=created_at,
                    updated_at=updated_at,
                    closed_at=closed_at,
                    project_id=project_id,  # 👈 ДОБАВЛЕНО
                    last_synced_at=datetime.utcnow(),
                    html_url=issue.html_url
                )
                self.db.add(new_issue)
                created_count += 1
            
            # 3. СОХРАНЯЕМ СОБЫТИЯ (CHANGELOG)
            try:
                events = await client.get_issue_events(owner, repo, issue.number)
                
                for event in events:
                    existing_event = self.db.query(GithubIssueEvent).filter(
                        GithubIssueEvent.external_event_id == event.id
                    ).first()
                    
                    if not existing_event:
                        detail_login = None
                        detail_id = None
                        
                        if event.assignee:
                            detail_login = event.assignee.login
                            detail_id = event.assignee.id
                        elif event.label:
                            detail_login = event.label.name
                        elif event.milestone:
                            detail_login = event.milestone.title
                        
                        event_created_at = None
                        if event.created_at:
                            try:
                                event_created_at = datetime.fromisoformat(
                                    event.created_at.replace('Z', '+00:00')
                                )
                            except:
                                event_created_at = datetime.utcnow()
                        
                        github_event = GithubIssueEvent(
                            issue_id=issue.id,
                            repo_full_name=repo_full_name,
                            event_type=event.event,
                            external_event_id=event.id,
                            actor_login=event.actor.login if event.actor else None,
                            actor_id=event.actor.id if event.actor else None,
                            detail_login=detail_login,
                            detail_id=detail_id,
                            commit_id=event.commit_id,
                            commit_url=event.commit_url,
                            state=event.state,
                            created_at=event_created_at
                        )
                        self.db.add(github_event)
                        
            except Exception as e:
                logger.warning(f"Failed to fetch events for issue {issue.number}: {e}")
        
        self.db.commit()
        
        return {
            "created": created_count,
            "updated": updated_count,
            "total": created_count + updated_count,
            "repo_full_name": repo_full_name,
            "instance_id": instance_id
        }

    async def sync_user_repos_issues(self, user_id: int, instance_id: str) -> dict:
        """
        Синхронизация issues из всех репозиториев пользователя.
        
        Args:
            user_id: ID пользователя
            instance_id: GitHub username
        
        Returns:
            dict с результатами для каждого репозитория
        """
        from app.github.client import GitHubClient
        
        token = self._get_github_token(user_id, instance_id)
        client = GitHubClient(
            access_token=token.access_token,
            instance_id=instance_id
        )
        
        # Получаем все репозитории
        repos = await client.get_repos()
        
        results = {}
        for repo in repos:
            if repo.private is True or repo.name.endswith('.git'):
                continue
            
            try:
                result = await self.sync_repo_issues_async(user_id, instance_id, repo.full_name)
                results[repo.full_name] = result
                logger.info(f"Synced {repo.full_name}: {result}")
            except Exception as e:
                logger.error(f"Failed to sync {repo.full_name}: {e}")
                results[repo.full_name] = {"error": str(e)}
        
        return results
