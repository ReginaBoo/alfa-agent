"""
API эндпоинты для интеграции с GitHub.
"""
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import IntegrationToken
from app.core.dependencies import get_current_user
from app.workers.queues import sync_github_queue
from app.workers.tasks import sync_github_task, sync_github_all_repos_task
from app.services.github_sync_service import GithubSyncService
from app.services.github_pr_sync_service import GithubPRSyncService
from app.services.github_project_link_service import link_repo_to_project
from app.services.cache_service import cache_service

router = APIRouter(prefix="/github", tags=["GitHub"])

def get_user_id(current_user):
    """Извлекает user_id из current_user (поддержка объекта User или dict)"""
    # Если это объект User из БД (теперь так и есть)
    if hasattr(current_user, 'id'):
        return current_user.id
    # Если это словарь (страховка на будущее)
    elif isinstance(current_user, dict):
        return current_user.get('id')
    else:
        raise HTTPException(500, f"Unexpected current_user type: {type(current_user)}")


# ================= MODELS =================

class CreateIssueRequest(BaseModel):
    title: str
    body: Optional[str] = None
    assignee: Optional[str] = None
    labels: Optional[List[str]] = None
    milestone: Optional[int] = None


class UpdateIssueRequest(BaseModel):
    state: Optional[str] = None
    title: Optional[str] = None
    body: Optional[str] = None
    assignee: Optional[str] = None
    labels: Optional[List[str]] = None
    milestone: Optional[int] = None


class LinkRepoToProjectRequest(BaseModel):
    project_key: str
    repo_full_name: str


# ================= HELPERS =================

def get_token(instance_id: str, db: Session, user_id: int) -> IntegrationToken:
    """Получает токен GitHub по instance_id (username)"""
    token = db.query(IntegrationToken).filter(
        IntegrationToken.instance_id == instance_id,
        IntegrationToken.user_id == user_id,
        IntegrationToken.provider == "github"
    ).first()
    
    if not token:
        raise HTTPException(status_code=404, detail="GitHub account not found")
    
    return token


async def _make_github_request(
    token: IntegrationToken,
    path: str,
    method: str = "GET",
    params: dict = None,
    json_data: dict = None,
    db: Session = None,
    user_id: int = None
):
    """Асинхронный запрос к GitHub API с автопродлением токена"""
    url = f"https://api.github.com/{path}"
    headers = {
        "Authorization": f"Bearer {token.access_token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Alpha-Agent"
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for attempt in range(2):
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_data
            )
            
            if response.status_code == 401 and attempt == 0:
                from app.services.token_refresh_service import TokenRefreshService
                await TokenRefreshService.update_github_token_async(db, user_id, token.instance_id)
                token = get_token(token.instance_id, db, user_id)
                headers["Authorization"] = f"Bearer {token.access_token}"
                continue
            
            response.raise_for_status()
            return response.json()
        
        raise HTTPException(401, "Token refresh failed")


# ================= AUTH =================

@router.get("/connect")
def get_auth_url():
    """Получить URL для авторизации через GitHub OAuth"""
    from app.github.oauth import get_authorization_url
    import secrets
    
    state = secrets.token_urlsafe(32)
    auth_url = get_authorization_url(state)
    
    return {
        "success": True,
        "auth_url": auth_url,
        "state": state
    }


# ================= USER =================

@router.get("/me")
async def get_github_user_info(
    instance_id: str = Query(..., description="GitHub username"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получить информацию о текущем пользователе GitHub"""
    token = get_token(instance_id, db, get_user_id(current_user))
    
    try:
        data = await _make_github_request(
            token=token,
            path="user",
            db=db,
            user_id=get_user_id(current_user) 
        )
        
        return {
            "success": True,
            "user": data
        }
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"GitHub API error: {str(e)}")


# ================= REPOSITORIES =================

@router.get("/repos")
async def get_repos(
    instance_id: str = Query(..., description="GitHub username"),
    affiliation: str = Query("owner,collaborator,organization_member"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получить список репозиториев пользователя"""
    from app.db.models import IntegrationToken
    
    token = get_token(instance_id, db, get_user_id(current_user))
    
    if not token:
        raise HTTPException(status_code=404, detail="GitHub account not found")
    
    try:
        data = await _make_github_request(
            token=token,
            path="user/repos",
            params={"affiliation": affiliation, "per_page": 100},
            db=db,
            user_id=get_user_id(current_user)
        )
        
        repos = [
            {
                "id": r.get("id"),
                "name": r.get("name"),
                "full_name": r.get("full_name"),
                "private": r.get("private"),
                "description": r.get("description"),
                "html_url": r.get("html_url"),
                "created_at": r.get("created_at"),
                "updated_at": r.get("updated_at")
            }
            for r in data
        ]
        
        return {
            "success": True,
            "total": len(repos),
            "repos": repos
        }
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"GitHub API error: {str(e)}")


# ================= ISSUES =================

@router.get("/issues")
async def get_issues(
    repo_full_name: str = Query(..., description="Полное имя репозитория (owner/repo)"),
    instance_id: str = Query(..., description="GitHub username"),
    state: str = Query("all", description="open, closed или all"),
    per_page: int = Query(100, ge=1, le=100),
    page: int = Query(1, ge=1),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получить список issues из репозитория"""
    token = get_token(instance_id, db, get_user_id(current_user))
    
    try:
        data = await _make_github_request(
            token=token,
            path=f"repos/{repo_full_name}/issues",
            params={"state": state, "per_page": per_page, "page": page},
            db=db,
            user_id=get_user_id(current_user)
        )
        
        issues = [
            {
                "id": i.get("id"),
                "number": i.get("number"),
                "title": i.get("title"),
                "state": i.get("state"),
                "locked": i.get("locked"),
                "labels": [l.get("name") for l in i.get("labels", [])],
                "assignees": [a.get("login") for a in i.get("assignees", [])],
                "user": i.get("user", {}).get("login"),
                "created_at": i.get("created_at"),
                "updated_at": i.get("updated_at"),
                "closed_at": i.get("closed_at"),
                "html_url": i.get("html_url")
            }
            for i in data
            if "pull_request" not in i  # Игнорируем PR
        ]
        
        return {
            "success": True,
            "total": len(issues),
            "issues": issues
        }
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"GitHub API error: {str(e)}")


@router.get("/issues/{issue_number}")
async def get_issue(
    issue_number: int,
    repo_full_name: str = Query(..., description="Полное имя репозитория"),
    instance_id: str = Query(..., description="GitHub username"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получить конкретный issue"""
    token = get_token(instance_id, db, get_user_id(current_user))
    
    try:
        data = await _make_github_request(
            token=token,
            path=f"repos/{repo_full_name}/issues/{issue_number}",
            db=db,
            user_id=get_user_id(current_user)
        )
        
        return {
            "success": True,
            "issue": data
        }
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"GitHub API error: {str(e)}")


@router.post("/issues")
async def create_issue(
    repo_full_name: str = Query(..., description="Полное имя репозитория"),
    instance_id: str = Query(..., description="GitHub username"),
    issue_data: CreateIssueRequest = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Создать новый issue"""
    token = get_token(instance_id, db, get_user_id(current_user))
    
    payload = {
        "title": issue_data.title
    }
    
    if issue_data.body:
        payload["body"] = issue_data.body
    if issue_data.assignee:
        payload["assignee"] = issue_data.assignee
    if issue_data.labels:
        payload["labels"] = issue_data.labels
    if issue_data.milestone:
        payload["milestone"] = issue_data.milestone
    
    try:
        data = await _make_github_request(
            token=token,
            path=f"repos/{repo_full_name}/issues",
            method="POST",
            json_data=payload,
            db=db,
            user_id=get_user_id(current_user)
        )
        
        return {
            "success": True,
            "issue": {
                "id": data.get("id"),
                "number": data.get("number"),
                "title": data.get("title"),
                "html_url": data.get("html_url")
            }
        }
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"GitHub API error: {str(e)}")


@router.patch("/issues/{issue_number}")
async def update_issue(
    issue_number: int,
    repo_full_name: str = Query(..., description="Полное имя репозитория"),
    instance_id: str = Query(..., description="GitHub username"),
    issue_data: UpdateIssueRequest = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Обновить существующий issue"""
    token = get_token(instance_id, db, get_user_id(current_user))
    
    payload = {}
    if issue_data.state:
        payload["state"] = issue_data.state
    if issue_data.title:
        payload["title"] = issue_data.title
    if issue_data.body:
        payload["body"] = issue_data.body
    if issue_data.assignee:
        payload["assignee"] = issue_data.assignee
    if issue_data.labels:
        payload["labels"] = issue_data.labels
    if issue_data.milestone:
        payload["milestone"] = issue_data.milestone
    
    try:
        data = await _make_github_request(
            token=token,
            path=f"repos/{repo_full_name}/issues/{issue_number}",
            method="PATCH",
            json_data=payload,
            db=db,
            user_id=get_user_id(current_user)
        )
        
        return {
            "success": True,
            "issue": {
                "id": data.get("id"),
                "number": data.get("number"),
                "title": data.get("title"),
                "state": data.get("state"),
                "html_url": data.get("html_url")
            }
        }
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"GitHub API error: {str(e)}")


# ================= COMMENTS =================

@router.get("/issues/{issue_number}/comments")
async def get_issue_comments(
    issue_number: int,
    repo_full_name: str = Query(..., description="Полное имя репозитория"),
    instance_id: str = Query(..., description="GitHub username"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получить комментарии к issue"""
    token = get_token(instance_id, db, get_user_id(current_user))
    
    try:
        data = await _make_github_request(
            token=token,
            path=f"repos/{repo_full_name}/issues/{issue_number}/comments",
            db=db,
            user_id=get_user_id(current_user)
        )
        
        return {
            "success": True,
            "comments": data
        }
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"GitHub API error: {str(e)}")


@router.post("/issues/{issue_number}/comments")
async def create_comment(
    issue_number: int,
    repo_full_name: str = Query(..., description="Полное имя репозитория"),
    instance_id: str = Query(..., description="GitHub username"),
    body: str = Query(..., description="Текст комментария"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Добавить комментарий к issue"""
    token = get_token(instance_id, db, get_user_id(current_user))
    
    payload = {"body": body}
    
    try:
        data = await _make_github_request(
            token=token,
            path=f"repos/{repo_full_name}/issues/{issue_number}/comments",
            method="POST",
            json_data=payload,
            db=db,
            user_id=get_user_id(current_user)
        )
        
        return {
            "success": True,
            "comment": data
        }
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"GitHub API error: {str(e)}")


# ================= EVENTS / TIMELINE =================

@router.get("/issues/{issue_number}/events")
async def get_issue_events(
    issue_number: int,
    repo_full_name: str = Query(..., description="Полное имя репозитория"),
    instance_id: str = Query(..., description="GitHub username"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получить события (events) для issue"""
    token = get_token(instance_id, db, get_user_id(current_user))
    
    try:
        data = await _make_github_request(
            token=token,
            path=f"repos/{repo_full_name}/issues/{issue_number}/events",
            db=db,
            user_id=get_user_id(current_user)
        )
        
        return {
            "success": True,
            "events": data
        }
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"GitHub API error: {str(e)}")


@router.get("/issues/{issue_number}/timeline")
async def get_issue_timeline(
    issue_number: int,
    repo_full_name: str = Query(..., description="Полное имя репозитория"),
    instance_id: str = Query(..., description="GitHub username"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получить детальную временную шкалу issue"""
    token = get_token(instance_id, db, get_user_id(current_user))
    
    try:
        data = await _make_github_request(
            token=token,
            path=f"repos/{repo_full_name}/issues/{issue_number}/timeline",
            db=db,
            user_id=get_user_id(current_user)
        )
        
        return {
            "success": True,
            "timeline": data
        }
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"GitHub API error: {str(e)}")


# ================= SYNC =================

@router.post("/sync/{repo_full_name:path}")
async def sync_issues(  
    repo_full_name: str,
    instance_id: str = Query(..., description="GitHub username"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Синхронизация issues репозитория в БД"""
    try:
        sync_service = GithubSyncService(db)
        result = await sync_service.sync_repo_issues_async(  
            user_id=get_user_id(current_user),  # ← ИСПРАВИТЬ
            instance_id=instance_id,
            repo_full_name=repo_full_name
        )
        return {
            "success": True,
            "message": f"Synced {result['total']} issues",
            "details": result
        }
    except Exception as e:
        raise HTTPException(500, f"Sync failed: {str(e)}")


@router.post("/sync-async/{repo_full_name:path}")
async def sync_issues_async(
    repo_full_name: str,
    instance_id: str = Query(..., description="GitHub username"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Асинхронная синхронизация issues репозитория в БД через очередь."""
    try:
        user_id = get_user_id(current_user)  # ← ДОБАВИТЬ
        job = sync_github_queue.enqueue(
            sync_github_task,
            args=(user_id, instance_id, repo_full_name),  # ← ИСПРАВИТЬ
            job_timeout="300s",
            result_ttl=3600,
            failure_ttl=3600
        )
        
        return {
            "success": True,
            "message": f"Sync for repo {repo_full_name} queued",
            "data": {
                "job_id": job.id,
                "status": "queued",
                "repo_full_name": repo_full_name,
                "instance_id": instance_id
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to queue sync: {str(e)}")


@router.post("/sync-all-async")
async def sync_all_repos_async(
    instance_id: str = Query(..., description="GitHub username"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Асинхронная синхронизация issues из всех репозиториев пользователя."""
    try:
        user_id = get_user_id(current_user)  # ← ДОБАВИТЬ
        job = sync_github_queue.enqueue(
            sync_github_all_repos_task,
            args=(user_id, instance_id),  # ← ИСПРАВИТЬ
            job_timeout="600s",
            result_ttl=3600,
            failure_ttl=3600
        )
        
        return {
            "success": True,
            "message": f"Sync for all repos of {instance_id} queued",
            "data": {
                "job_id": job.id,
                "status": "queued",
                "instance_id": instance_id
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to queue sync: {str(e)}")




@router.post("/link-to-project")
def link_repo_to_project_endpoint(
    data: LinkRepoToProjectRequest,
    instance_id: str = Query(..., description="GitHub username"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Связывает GitHub репозиторий с проектом в системе."""
    try:
        result = link_repo_to_project(
            db=db,
            repo_full_name=data.repo_full_name,
            project_key=data.project_key,
            user_id=get_user_id(current_user)  # ← ИСПРАВИТЬ
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to link: {str(e)}")
    


@router.get("/test-token")
async def test_token(
    instance_id: str = Query(..., description="GitHub username"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Тестовый эндпоинт для отладки"""
    from app.db.models import IntegrationToken
    
    user_id = current_user.id if hasattr(current_user, 'id') else current_user.get('id')
    
    token = db.query(IntegrationToken).filter(
        IntegrationToken.instance_id == instance_id,
        IntegrationToken.user_id == user_id,
        IntegrationToken.provider == "github"
    ).first()
    
    return {
        "user_id": user_id,
        "instance_id": instance_id,
        "token_found": token is not None,
        "token_id": token.id if token else None,
        "current_user_type": str(type(current_user))
    }


# ================= PULL REQUESTS =================

@router.get("/pulls")
async def get_pull_requests(
    repo_full_name: str = Query(..., description="Полное имя репозитория (owner/repo)"),
    instance_id: str = Query(..., description="GitHub username"),
    state: str = Query("all", description="open, closed или all"),
    per_page: int = Query(100, ge=1, le=100),
    page: int = Query(1, ge=1),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получить список Pull Requests из репозитория"""
    token = get_token(instance_id, db, get_user_id(current_user))
    
    parts = repo_full_name.split("/")
    if len(parts) != 2:
        raise HTTPException(400, "Invalid repo_full_name format. Use owner/repo")
    owner, repo = parts
    
    try:
        from app.github.client import GitHubClient
        client = GitHubClient(
            access_token=token.access_token,
            instance_id=instance_id
        )
        
        prs = await client.get_pull_requests(
            owner=owner,
            repo=repo,
            state=state,
            per_page=per_page,
            page=page
        )
        
        result = [
            {
                "id": pr.id,
                "number": pr.number,
                "title": pr.title,
                "state": pr.state,
                "merged": pr.merged,
                "merged_at": pr.merged_at,
                "author": pr.user.login if pr.user else None,
                "created_at": pr.created_at,
                "updated_at": pr.updated_at,
                "closed_at": pr.closed_at,
                "head_branch": pr.head.get('ref') if pr.head else None,
                "base_branch": pr.base.get('ref') if pr.base else None,
                "additions": pr.additions,
                "deletions": pr.deletions,
                "comments_count": pr.comments,
                "review_comments_count": pr.review_comments,
                "requested_reviewers": [r.login for r in pr.requested_reviewers],
                "html_url": pr.html_url
            }
            for pr in prs
        ]
        
        return {
            "success": True,
            "total": len(result),
            "pull_requests": result
        }
    except Exception as e:
        raise HTTPException(502, f"GitHub API error: {str(e)}")


@router.get("/pulls/{pr_number}/reviews")
async def get_pull_request_reviews(
    pr_number: int,
    repo_full_name: str = Query(..., description="Полное имя репозитория"),
    instance_id: str = Query(..., description="GitHub username"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получить ревью для Pull Request"""
    token = get_token(instance_id, db, get_user_id(current_user))
    
    parts = repo_full_name.split("/")
    if len(parts) != 2:
        raise HTTPException(400, "Invalid repo_full_name format")
    owner, repo = parts
    
    try:
        from app.github.client import GitHubClient
        client = GitHubClient(
            access_token=token.access_token,
            instance_id=instance_id
        )
        
        reviews = await client.get_pull_request_reviews(owner, repo, pr_number)
        
        result = [
            {
                "id": review.id,
                "user": review.user.login if review.user else None,
                "state": review.state,
                "body": review.body,
                "submitted_at": review.submitted_at,
                "html_url": review.html_url
            }
            for review in reviews
        ]
        
        return {
            "success": True,
            "total": len(result),
            "reviews": result
        }
    except Exception as e:
        raise HTTPException(502, f"GitHub API error: {str(e)}")


@router.get("/commits")
async def get_commits(
    repo_full_name: str = Query(..., description="Полное имя репозитория"),
    instance_id: str = Query(..., description="GitHub username"),
    per_page: int = Query(100, ge=1, le=100),
    page: int = Query(1, ge=1),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получить список коммитов из репозитория"""
    token = get_token(instance_id, db, get_user_id(current_user))
    
    parts = repo_full_name.split("/")
    if len(parts) != 2:
        raise HTTPException(400, "Invalid repo_full_name format")
    owner, repo = parts
    
    try:
        from app.github.client import GitHubClient
        client = GitHubClient(
            access_token=token.access_token,
            instance_id=instance_id
        )
        
        commits = await client.get_commits(
            owner=owner,
            repo=repo,
            per_page=per_page,
            page=page
        )
        
        result = []
        for commit in commits:
            commit_detail = commit.get('commit', {})
            author = commit.get('author', {})
            stats = commit.get('stats', {})
            
            result.append({
                "sha": commit.get('sha'),
                "author_login": author.get('login'),
                "author_name": commit_detail.get('author', {}).get('name'),
                "message": commit_detail.get('message', '')[:200],
                "committed_at": commit_detail.get('author', {}).get('date'),
                "additions": stats.get('additions', 0),
                "deletions": stats.get('deletions', 0),
                "total_changes": stats.get('total', 0),
                "html_url": commit.get('html_url')
            })
        
        return {
            "success": True,
            "total": len(result),
            "commits": result
        }
    except Exception as e:
        raise HTTPException(502, f"GitHub API error: {str(e)}")


# ================= SYNC =================

@router.post("/sync-prs/{repo_full_name:path}")
async def sync_pull_requests(
    repo_full_name: str,
    instance_id: str = Query(..., description="GitHub username"),
    sync_reviews: bool = Query(True, description="Синхронизировать ревью"),
    sync_commits: bool = Query(True, description="Синхронизировать коммиты из PR"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Синхронизация Pull Requests, Reviews и Commits в БД"""
    try:
        sync_service = GithubPRSyncService(db)
        result = await sync_service.sync_repo_pull_requests(
            user_id=get_user_id(current_user),
            instance_id=instance_id,
            repo_full_name=repo_full_name,
            sync_reviews=sync_reviews,
            sync_commits=sync_commits
        )
        
        # Инвалидируем кэш после синхронизации
        cache_service.delete_pattern(f"projects_stats:{current_user.id}:*")
        cache_service.delete_pattern(f"ai_insights:{current_user.id}")
        cache_service.delete_pattern(f"activity_trends:*")
        
        return {
            "success": True,
            "message": f"Sync completed",
            "details": result
        }
    except Exception as e:
        raise HTTPException(500, f"Sync failed: {str(e)}")


@router.post("/sync-commits/{repo_full_name:path}")
async def sync_commits_full(
    repo_full_name: str,
    instance_id: str = Query(..., description="GitHub username"),
    since_days: int = Query(30, description="Последние N дней"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Синхронизация ВСЕХ коммитов репозитория за период"""
    try:
        sync_service = GithubPRSyncService(db)
        result = await sync_service.sync_repo_commits_full(
            user_id=get_user_id(current_user),
            instance_id=instance_id,
            repo_full_name=repo_full_name,
            since_days=since_days
        )
        return {
            "success": True,
            "message": f"Commits sync completed",
            "details": result
        }
    except Exception as e:
        raise HTTPException(500, f"Sync failed: {str(e)}")


# ================= METRICS =================

@router.get("/metrics/pr-stats/{repo_full_name:path}")
async def get_pr_metrics(
    repo_full_name: str,
    instance_id: str = Query(..., description="GitHub username"),
    project_key: str = Query(..., description="Ключ проекта Jira"),
    period_days: int = Query(30, description="Период в днях"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получить метрики по Pull Requests для проекта"""
    from app.services.github_project_link_service import get_project_by_key
    
    project = get_project_by_key(db, project_key)
    if not project:
        raise HTTPException(404, f"Project {project_key} not found")
    
    try:
        from app.services.metrics.pr_metrics import get_pr_stats_for_project
        
        stats = get_pr_stats_for_project(db, project.id, period_days)
        
        return {
            "success": True,
            "project_key": project_key,
            "repo_full_name": repo_full_name,
            "period_days": period_days,
            "stats": stats
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to calculate metrics: {str(e)}")




@router.get("/debug-token")
async def debug_token(
    instance_id: str = Query(..., description="GitHub username"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Диагностический эндпоинт"""
    from app.db.models import IntegrationToken
    
    user_id = get_user_id(current_user)
    
    # Поиск токена
    token = db.query(IntegrationToken).filter(
        IntegrationToken.instance_id == instance_id,
        IntegrationToken.user_id == user_id,
        IntegrationToken.provider == "github"
    ).first()
    
    # Поиск всех GitHub токенов для user_id
    all_tokens = db.query(IntegrationToken).filter(
        IntegrationToken.user_id == user_id,
        IntegrationToken.provider == "github"
    ).all()
    
    return {
        "user_id_from_get_user_id": user_id,
        "current_user_type": str(type(current_user)),
        "current_user_repr": str(current_user),
        "token_found": token is not None,
        "token_id": token.id if token else None,
        "all_tokens_for_user": [
            {"id": t.id, "instance_id": t.instance_id} for t in all_tokens
        ],
        "all_tokens_in_db": [
            {"id": t.id, "user_id": t.user_id, "instance_id": t.instance_id} 
            for t in db.query(IntegrationToken).filter(IntegrationToken.provider == "github").all()
        ]
    }


@router.get("/direct-token-check")
async def direct_token_check(
    instance_id: str = Query(..., description="GitHub username"),
    db: Session = Depends(get_db)
):
    """Прямая проверка токена без current_user"""
    from app.db.models import IntegrationToken
    
    # Ищем токен для user_id=1
    token = db.query(IntegrationToken).filter(
        IntegrationToken.instance_id == instance_id,
        IntegrationToken.user_id == 1,
        IntegrationToken.provider == "github"
    ).first()
    
    return {
        "token_found": token is not None,
        "token_id": token.id if token else None,
        "instance_id": instance_id,
        "user_id_check": 1
    }