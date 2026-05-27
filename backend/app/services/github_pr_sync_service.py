"""
Дополнительные методы для синхронизации Pull Requests, Commits и Reviews
"""
import logging
import re
from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.db.models import IntegrationToken, RawEvent
from app.db.models.normalized import (
    GithubPullRequest, GithubPullRequestReview, GithubCommit
)
from app.services.github_project_link_service import get_project_by_repo

logger = logging.getLogger(__name__)


class GithubPRSyncService:
    """Синхронизация Pull Requests, Commits и Reviews из GitHub"""

    def __init__(self, db: Session):
        self.db = db

    def _get_github_token(self, user_id: int, instance_id: str) -> IntegrationToken:
        """Получает токен GitHub для пользователя и инстанса"""
        from app.db.models import IntegrationToken
        
        token = self.db.query(IntegrationToken).filter(
            IntegrationToken.user_id == user_id,
            IntegrationToken.instance_id == instance_id,
            IntegrationToken.provider == "github"
        ).first()

        if not token:
            raise ValueError(f"Token not found for GitHub user {instance_id}")
        
        return token

    def _parse_jira_key(self, message: str) -> str:
        """
        Парсит Jira-ключ из сообщения коммита.
        Ищет паттерны типа: PROJ-123, ABC-456, PROJECT-789
        """
        if not message:
            return None
        
        # Паттерн: заглавные буквы, дефис, цифры
        match = re.search(r'\b([A-Z]+-\d+)\b', message)
        return match.group(1) if match else None

    def _parse_datetime(self, dt_str: str) -> datetime:
        """Безопасный парсинг datetime из ISO строки"""
        if not dt_str:
            return None
        try:
            return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        except Exception:
            return datetime.utcnow()

    async def sync_repo_pull_requests(
        self,
        user_id: int,
        instance_id: str,
        repo_full_name: str,
        sync_reviews: bool = True,
        sync_commits: bool = True
    ) -> Dict[str, int]:
        """
        Синхронизирует Pull Requests, опционально Reviews и Commits.
        
        Args:
            user_id: ID пользователя
            instance_id: GitHub username
            repo_full_name: owner/repo
            sync_reviews: Синхронизировать ли ревью
            sync_commits: Синхронизировать ли коммиты
            
        Returns:
            dict со статистикой
        """
        from app.github.client import GitHubClient
        
        token = self._get_github_token(user_id, instance_id)
        client = GitHubClient(
            access_token=token.access_token,
            instance_id=instance_id
        )
        
        parts = repo_full_name.split("/")
        if len(parts) != 2:
            raise ValueError(f"Invalid repo_full_name: {repo_full_name}")
        owner, repo = parts
        
        # Находим проект
        project = get_project_by_repo(self.db, repo_full_name)
        project_id = project.id if project else None
        
        # Получаем все PR
        all_prs = []
        page = 1
        per_page = 100
        
        while True:
            prs = await client.get_pull_requests(
                owner=owner,
                repo=repo,
                state="all",
                per_page=per_page,
                page=page
            )
            
            if not prs:
                break
            
            all_prs.extend(prs)
            
            if len(prs) < per_page:
                break
            
            page += 1
            logger.info(f"Fetched page {page} of PRs for {repo_full_name}")
        
        # Статистика
        stats = {
            "prs_created": 0,
            "prs_updated": 0,
            "reviews_synced": 0,
            "commits_synced": 0
        }
        
        for pr in all_prs:
            try:
                # 1. Сохраняем сырые данные
                raw_event = RawEvent(
                    source="github",
                    event_type="pull_request",
                    external_id=str(pr.id),
                    project_integration_id=None,
                    payload=pr.model_dump() if hasattr(pr, 'model_dump') else pr.dict(),
                    timestamp=datetime.utcnow()
                )
                self.db.add(raw_event)
                
                # 2. Находим или создаём PR
                existing_pr = self.db.query(GithubPullRequest).filter(
                    GithubPullRequest.pr_id == pr.id
                ).first()
                
                # Парсим данные
                created_at = self._parse_datetime(pr.created_at)
                updated_at = self._parse_datetime(pr.updated_at)
                closed_at = self._parse_datetime(pr.closed_at)
                merged_at = self._parse_datetime(pr.merged_at)
                
                # Ревьюверы
                reviewers = [r.login for r in pr.requested_reviewers] if pr.requested_reviewers else []
                
                # Head info
                head_branch = pr.head.get('ref') if pr.head else None
                head_sha = pr.head.get('sha') if pr.head else None
                base_branch = pr.base.get('ref') if pr.base else None
                
                if existing_pr:
                    # Обновляем
                    existing_pr.title = pr.title
                    existing_pr.body = pr.body
                    existing_pr.state = pr.state
                    existing_pr.status = "merged" if pr.merged else pr.state
                    existing_pr.mergeable = pr.mergeable
                    existing_pr.mergeable_state = pr.mergeable_state
                    existing_pr.merged = pr.merged
                    existing_pr.merged_at = merged_at
                    existing_pr.merged_by_login = pr.merged_by.login if pr.merged_by else None
                    existing_pr.merged_by_id = pr.merged_by.id if pr.merged_by else None
                    existing_pr.requested_reviewers = reviewers
                    existing_pr.created_at = created_at
                    existing_pr.updated_at = updated_at
                    existing_pr.closed_at = closed_at
                    existing_pr.comments_count = pr.comments
                    existing_pr.review_comments_count = pr.review_comments
                    existing_pr.commits_count = pr.commits
                    existing_pr.additions = pr.additions
                    existing_pr.deletions = pr.deletions
                    existing_pr.head_branch = head_branch
                    existing_pr.base_branch = base_branch
                    existing_pr.head_sha = head_sha
                    existing_pr.project_id = project_id
                    existing_pr.last_synced_at = datetime.utcnow()
                    existing_pr.snapshot_version = (existing_pr.snapshot_version or 0) + 1
                    
                    stats["prs_updated"] += 1
                else:
                    # Создаём новый
                    new_pr = GithubPullRequest(
                        pr_id=pr.id,
                        pr_number=pr.number,
                        repo_full_name=repo_full_name,
                        repo_id=pr.id,
                        title=pr.title,
                        body=pr.body,
                        state=pr.state,
                        status="merged" if pr.merged else pr.state,
                        author_login=pr.user.login if pr.user else None,
                        author_id=pr.user.id if pr.user else None,
                        mergeable=pr.mergeable,
                        mergeable_state=pr.mergeable_state,
                        merged=pr.merged,
                        merged_at=merged_at,
                        merged_by_login=pr.merged_by.login if pr.merged_by else None,
                        merged_by_id=pr.merged_by.id if pr.merged_by else None,
                        requested_reviewers=reviewers,
                        created_at=created_at,
                        updated_at=updated_at,
                        closed_at=closed_at,
                        comments_count=pr.comments,
                        review_comments_count=pr.review_comments,
                        commits_count=pr.commits,
                        additions=pr.additions,
                        deletions=pr.deletions,
                        head_branch=head_branch,
                        base_branch=base_branch,
                        head_sha=head_sha,
                        project_id=project_id,
                        last_synced_at=datetime.utcnow(),
                        html_url=pr.html_url
                    )
                    self.db.add(new_pr)
                    stats["prs_created"] += 1
                
                # 3. Синхронизируем ревью
                if sync_reviews and pr.merged:
                    reviews = await client.get_pull_request_reviews(owner, repo, pr.number)
                    
                    for review in reviews:
                        existing_review = self.db.query(GithubPullRequestReview).filter(
                            GithubPullRequestReview.review_id == review.id
                        ).first()
                        
                        if not existing_review:
                            submitted_at = self._parse_datetime(review.submitted_at)
                            
                            new_review = GithubPullRequestReview(
                                review_id=review.id,
                                pr_id=pr.id,
                                repo_full_name=repo_full_name,
                                user_login=review.user.login if review.user else None,
                                user_id=review.user.id if review.user else None,
                                state=review.state,
                                body=review.body,
                                submitted_at=submitted_at,
                                html_url=review.html_url,
                                pull_request_url=review.pull_request_url
                            )
                            self.db.add(new_review)
                            stats["reviews_synced"] += 1
                
                # 4. Синхронизируем коммиты из PR
                if sync_commits and pr.merged:
                    pr_commits = await client.get_pull_request_commits(owner, repo, pr.number)
                    
                    for commit_data in pr_commits:
                        commit_sha = commit_data.get('sha')
                        
                        existing_commit = self.db.query(GithubCommit).filter(
                            GithubCommit.commit_sha == commit_sha,
                            GithubCommit.repo_full_name == repo_full_name
                        ).first()
                        
                        if not existing_commit:
                            commit_detail = await client.get_commit(owner, repo, commit_sha)
                            
                            # Парсим коммит
                            commit_msg = commit_detail.get('commit', {}).get('message', '')
                            jira_key = self._parse_jira_key(commit_msg)
                            
                            author = commit_detail.get('author', {})
                            commit_author = commit_detail.get('commit', {}).get('author', {})
                            
                            # Статистика изменений
                            stats_data = commit_detail.get('stats', {})
                            additions = stats_data.get('additions', 0)
                            deletions = stats_data.get('deletions', 0)
                            total = stats_data.get('total', 0)
                            
                            committed_at = self._parse_datetime(commit_detail.get('commit', {}).get('author', {}).get('date'))
                            
                            new_commit = GithubCommit(
                                commit_sha=commit_sha,
                                repo_full_name=repo_full_name,
                                repo_id=pr.id,
                                author_login=author.get('login'),
                                author_id=author.get('id'),
                                author_name=commit_author.get('name'),
                                author_email=commit_author.get('email'),
                                message=commit_msg,
                                html_url=commit_detail.get('html_url'),
                                additions=additions,
                                deletions=deletions,
                                total_changes=total,
                                project_id=project_id,
                                committed_at=committed_at,
                                last_synced_at=datetime.utcnow()
                            )
                            self.db.add(new_commit)
                            stats["commits_synced"] += 1
                
            except Exception as e:
                logger.error(f"Error processing PR #{pr.number}: {e}")
                continue
        
        self.db.commit()
        
        logger.info(f"Synced PRs for {repo_full_name}: {stats}")
        return stats

    async def sync_repo_commits_full(
        self,
        user_id: int,
        instance_id: str,
        repo_full_name: str,
        since_days: int = 30
    ) -> Dict[str, int]:
        """
        Синхронизирует ВСЕ коммиты репозитория (не только из PR).
        Полезно для полного Activity Score.
        """
        from app.github.client import GitHubClient
        
        token = self._get_github_token(user_id, instance_id)
        client = GitHubClient(
            access_token=token.access_token,
            instance_id=instance_id
        )
        
        parts = repo_full_name.split("/")
        if len(parts) != 2:
            raise ValueError(f"Invalid repo_full_name: {repo_full_name}")
        owner, repo = parts
        
        project = get_project_by_repo(self.db, repo_full_name)
        project_id = project.id if project else None
        
        # Вычисляем since
        from datetime import timedelta
        since_date = datetime.utcnow() - timedelta(days=since_days)
        since_iso = since_date.isoformat() + "Z"
        
        all_commits = []
        page = 1
        per_page = 100
        
        while True:
            commits = await client.get_commits(
                owner=owner,
                repo=repo,
                per_page=per_page,
                page=page,
                since=since_iso
            )
            
            if not commits:
                break
            
            all_commits.extend(commits)
            
            if len(commits) < per_page:
                break
            
            page += 1
            logger.info(f"Fetched page {page} of commits for {repo_full_name}")
        
        synced_count = 0
        
        for commit_data in all_commits:
            try:
                commit_sha = commit_data.get('sha')
                
                existing = self.db.query(GithubCommit).filter(
                    GithubCommit.commit_sha == commit_sha,
                    GithubCommit.repo_full_name == repo_full_name
                ).first()
                
                if existing:
                    continue
                
                # Получаем детали
                commit_detail = await client.get_commit(owner, repo, commit_sha)
                
                commit_msg = commit_detail.get('commit', {}).get('message', '')
                jira_key = self._parse_jira_key(commit_msg)
                
                author = commit_detail.get('author', {})
                commit_author = commit_detail.get('commit', {}).get('author', {})
                
                stats_data = commit_detail.get('stats', {})
                additions = stats_data.get('additions', 0)
                deletions = stats_data.get('deletions', 0)
                total = stats_data.get('total', 0)
                
                committed_at = self._parse_datetime(commit_detail.get('commit', {}).get('author', {}).get('date'))
                
                new_commit = GithubCommit(
                    commit_sha=commit_sha,
                    repo_full_name=repo_full_name,
                    repo_id=None,
                    author_login=author.get('login'),
                    author_id=author.get('id'),
                    author_name=commit_author.get('name'),
                    author_email=commit_author.get('email'),
                    message=commit_msg,
                    html_url=commit_detail.get('html_url'),
                    additions=additions,
                    deletions=deletions,
                    total_changes=total,
                    project_id=project_id,
                    committed_at=committed_at,
                    last_synced_at=datetime.utcnow()
                )
                self.db.add(new_commit)
                synced_count += 1
                
            except Exception as e:
                logger.error(f"Error processing commit {commit_sha}: {e}")
                continue
        
        self.db.commit()
        
        logger.info(f"Synced {synced_count} commits for {repo_full_name}")
        return {"commits_synced": synced_count}

    async def sync_check_runs_for_pr(
        self,
        user_id: int,
        instance_id: str,
        repo_full_name: str,
        pr_number: int
    ) -> Dict[str, Any]:
        """
        Синхронизирует Check Runs (CI/CD статусы) для PR.
        Пока сохраняет в RawEvent, т.к. нет отдельной таблицы.
        """
        from app.github.client import GitHubClient
        
        token = self._get_github_token(user_id, instance_id)
        client = GitHubClient(
            access_token=token.access_token,
            instance_id=instance_id
        )
        
        parts = repo_full_name.split("/")
        if len(parts) != 2:
            raise ValueError(f"Invalid repo_full_name: {repo_full_name}")
        owner, repo = parts
        
        # Получаем PR для head_sha
        pr = await client.get_pull_request(owner, repo, pr_number)
        head_sha = pr.head.get('sha') if pr.head else None
        
        if not head_sha:
            return {"error": "No head_sha found"}
        
        # Получаем Check Runs
        check_runs = await client.get_check_runs(owner, repo, head_sha)
        
        # Анализируем статусы
        stats = {
            "total": len(check_runs),
            "success": 0,
            "failure": 0,
            "in_progress": 0,
            "other": 0
        }
        
        for check in check_runs:
            if check.status == "completed":
                if check.conclusion == "success":
                    stats["success"] += 1
                elif check.conclusion in ["failure", "cancelled"]:
                    stats["failure"] += 1
                else:
                    stats["other"] += 1
            elif check.status == "in_progress":
                stats["in_progress"] += 1
        
        # Сохраняем сырые данные
        raw_event = RawEvent(
            source="github",
            event_type="check_run",
            external_id=head_sha,
            project_integration_id=None,
            payload={
                "repo": repo_full_name,
                "pr_number": pr_number,
                "head_sha": head_sha,
                "check_runs": [c.model_dump() if hasattr(c, 'model_dump') else c.dict() for c in check_runs],
                "stats": stats
            },
            timestamp=datetime.utcnow()
        )
        self.db.add(raw_event)
        self.db.commit()
        
        return stats
