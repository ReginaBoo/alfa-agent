# app/endpoints/jira_endpoints.py

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import IntegrationToken
from app.core.dependencies import get_current_user
from app.workers.queues import sync_jira_queue
from app.workers.tasks import sync_jira_task
from app.services.project_sync_service import sync_projects_from_jira, refresh_all_project_statuses
from app.services.jira_sync_service import JiraSyncService
from app.jira.client import JiraClient
from app.services.token_service import TokenService


router = APIRouter()


# ================= MODELS =================

class CreateIssueRequest(BaseModel):
    project_key: str
    summary: str
    issue_type: str = "Task"
    description: Optional[str] = None
    assignee_account_id: Optional[str] = None
    priority: Optional[str] = None
    labels: Optional[List[str]] = None


class TransitionRequest(BaseModel):
    transition_id: str


class SyncProjectsRequest(BaseModel):
    sync_statuses: bool = True


# ================= HELPERS =================

def get_token(instance_name: str, db: Session, user_id: int) -> IntegrationToken:
    """Получает токен по имени сайта"""
    token = db.query(IntegrationToken).filter(
        IntegrationToken.instance_name == instance_name,
        IntegrationToken.user_id == user_id,
        IntegrationToken.provider == "jira"
    ).first()
    
    if not token:
        raise HTTPException(status_code=404, detail="Jira site not found")
    
    return token


def get_token_by_instance_id(instance_id: str, db: Session, user_id: int) -> IntegrationToken:
    """Получает токен по cloud_id"""
    token = db.query(IntegrationToken).filter(
        IntegrationToken.instance_id == instance_id,
        IntegrationToken.user_id == user_id,
        IntegrationToken.provider == "jira"
    ).first()
    
    if not token:
        raise HTTPException(status_code=404, detail="Jira site not found")
    
    return token


async def _make_jira_request(
    token: IntegrationToken,
    path: str,
    method: str = "GET",
    params: dict = None,
    json_data: dict = None,
    db: Session = None,
    user_id: int = None
):
    """Асинхронный запрос к Jira API с автопродлением токена"""
    url = f"https://api.atlassian.com/ex/jira/{token.instance_id}/rest/api/3/{path}"
    headers = {
        "Authorization": f"Bearer {token.access_token}",
        "Content-Type": "application/json"
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
                await TokenRefreshService.update_user_tokens_async(db, user_id)
                token = get_token_by_instance_id(token.instance_id, db, user_id)
                headers["Authorization"] = f"Bearer {token.access_token}"
                continue
            
            response.raise_for_status()
            return response.json()
        
        raise HTTPException(401, "Token refresh failed")


def get_jira_client(db: Session, user_id: int, instance_name: str) -> JiraClient:
    """Возвращает JiraClient для работы с API"""
    token = get_token(instance_name, db, user_id)
    from app.services.token_refresh_service import TokenRefreshService
    return JiraClient(
        access_token=token.access_token,
        refresh_token=token.refresh_token,
        token_service=TokenRefreshService(db, user_id)
    )


# ================= SITES =================

@router.get("/sites")
def get_sites(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    tokens = db.query(IntegrationToken).filter(
        IntegrationToken.user_id == current_user.id,
        IntegrationToken.provider == "jira"
    ).all()

    return {
        "success": True,
        "sites": [
            {
                "cloud_id": t.instance_id,
                "site_name": t.instance_name,
                "site_url": t.instance_url,
                "expires_at": t.expires_at.isoformat() if t.expires_at else None
            }
            for t in tokens
        ]
    }


# ================= PROJECTS =================

@router.get("/projects")
async def get_projects(
    instance_name: str = Query(...),
    search: Optional[str] = Query(None, description="Поиск по имени проекта"),
    sync_to_db: bool = Query(True, description="Синхронизировать проекты с БД"),
    sync_statuses: bool = Query(True, description="Синхронизировать статусы проектов"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    token = get_token(instance_name, db, current_user.id)
    
    try:
        # Синхронизация с БД (если включена)
        if sync_to_db:
            sync_result = sync_projects_from_jira(
                db=db,
                user_id=current_user.id,
                instance_name=instance_name,
                token_instance_id=token.instance_id,
                token_access_token=token.access_token,
                sync_statuses=sync_statuses  # ← НОВЫЙ ПАРАМЕТР
            )
        else:
            sync_result = None
        
        # Получаем проекты из Jira API для ответа
        data = await _make_jira_request(
            token=token,
            path="project",
            db=db,
            user_id=current_user.id
        )
        
        projects = [
            {"id": p.get("id"), "key": p.get("key"), "name": p.get("name")}
            for p in data
        ]
        
        # Фильтрация по имени
        if search:
            search_lower = search.lower()
            projects = [p for p in projects if search_lower in p["name"].lower()]
        
        result = {
            "success": True,
            "total_projects": len(projects),
            "projects": projects
        }
        
        if sync_result:
            result["sync"] = sync_result
        
        return result
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"Jira API error: {str(e)}")


@router.post("/projects/sync")
async def sync_projects_endpoint(
    instance_name: str = Query(...),
    sync_statuses: bool = Query(True, description="Синхронизировать статусы проектов"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Принудительная синхронизация проектов из Jira в БД.
    """
    try:
        result = sync_projects_from_jira(
            db=db,
            user_id=current_user.id,
            instance_name=instance_name,
            sync_statuses=sync_statuses
        )
        return {
            "success": True,
            "message": f"Synced {result['total']} projects",
            "details": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.post("/projects/refresh-statuses")
async def refresh_projects_statuses(
    instance_name: str = Query(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Принудительно обновляет статусы для всех проектов пользователя.
    """
    try:
        result = refresh_all_project_statuses(
            db=db,
            user_id=current_user.id,
            instance_name=instance_name
        )
        return {
            "success": True,
            "message": f"Refreshed {result['statuses_updated']} statuses for {result['projects_processed']} projects",
            "details": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Refresh failed: {str(e)}")


@router.get("/projects/with-statuses")
async def get_projects_with_statuses(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Возвращает проекты пользователя с их статусами из БД.
    """
    from app.services.project_sync_service import get_user_projects_with_metrics
    
    projects = get_user_projects_with_metrics(db, current_user.id)
    return {
        "success": True,
        "projects": projects
    }


# ================= ISSUES SEARCH =================

@router.get("/issues")
async def search_issues(
    instance_name: str = Query(...),
    jql: str = Query(...),
    start_at: int = Query(0, ge=0),
    max_results: int = Query(50, ge=1, le=100),
    fields: Optional[str] = Query("*all"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    token = get_token(instance_name, db, current_user.id)
    
    params = {
        "jql": jql,
        "startAt": start_at,
        "maxResults": max_results,
        "fields": fields
    }
    
    try:
        data = await _make_jira_request(
            token=token,
            path="search/jql",
            params=params,
            db=db,
            user_id=current_user.id
        )
        
        return {
            "success": True,
            "total": data.get("total", 0),
            "issues": data.get("issues", [])
        }
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"Jira API error: {str(e)}")


# ================= GET ISSUE BY KEY =================

@router.get("/issues/{issue_key}")
async def get_issue(
    issue_key: str,
    instance_name: str = Query(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    token = get_token(instance_name, db, current_user.id)
    
    try:
        data = await _make_jira_request(
            token=token,
            path=f"issue/{issue_key}",
            db=db,
            user_id=current_user.id
        )
        
        return {
            "success": True,
            "issue": data
        }
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"Jira API error: {str(e)}")


# ================= CREATE ISSUE =================

@router.post("/issues")
async def create_issue(
    instance_name: str = Query(...),
    issue_data: CreateIssueRequest = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    token = get_token(instance_name, db, current_user.id)
    
    payload = {
        "fields": {
            "project": {"key": issue_data.project_key},
            "summary": issue_data.summary,
            "issuetype": {"name": issue_data.issue_type}
        }
    }
    
    if issue_data.description:
        payload["fields"]["description"] = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": issue_data.description}
                    ]
                }
            ]
        }
    
    if issue_data.assignee_account_id:
        payload["fields"]["assignee"] = {"accountId": issue_data.assignee_account_id}
    
    if issue_data.priority:
        payload["fields"]["priority"] = {"name": issue_data.priority}
    
    if issue_data.labels:
        payload["fields"]["labels"] = issue_data.labels
    
    try:
        data = await _make_jira_request(
            token=token,
            path="issue",
            method="POST",
            json_data=payload,
            db=db,
            user_id=current_user.id
        )
        
        return {
            "success": True,
            "issue_key": data.get("key"),
            "issue_id": data.get("id")
        }
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"Jira API error: {str(e)}")


# ================= TRANSITION ISSUE =================

@router.post("/issues/{issue_key}/transitions")
async def transition_issue(
    issue_key: str,
    instance_name: str = Query(...),
    transition: TransitionRequest = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    token = get_token(instance_name, db, current_user.id)
    
    payload = {"transition": {"id": transition.transition_id}}
    
    try:
        await _make_jira_request(
            token=token,
            path=f"issue/{issue_key}/transitions",
            method="POST",
            json_data=payload,
            db=db,
            user_id=current_user.id
        )
        
        return {"success": True}
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"Jira API error: {str(e)}")


# ================= ISSUE CHANGELOG =================

@router.get("/issues/{issue_key}/changelog")
async def get_issue_changelog(
    issue_key: str,
    instance_name: str = Query(...),
    start_at: int = Query(0, ge=0, description="Начало выборки"),
    max_results: int = Query(50, ge=1, le=100, description="Количество записей"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    token = get_token(instance_name, db, current_user.id)
    
    try:
        # Получаем полный changelog
        data = await _make_jira_request(
            token=token,
            path=f"issue/{issue_key}/changelog",
            db=db,
            user_id=current_user.id
        )
        
        values = data.get("values", [])
        total = len(values)
        
        # Пагинация
        paginated_values = values[start_at:start_at + max_results]
        
        return {
            "success": True,
            "total": total,
            "start_at": start_at,
            "max_results": max_results,
            "has_next": start_at + max_results < total,
            "changelog": paginated_values
        }
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"Jira API error: {str(e)}")


# ================= SYNC PROJECT STATUSES =================

@router.post("/sync-statuses/{project_key}")
async def sync_project_statuses_endpoint(
    project_key: str,
    instance_name: str = Query(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Синхронизирует статусы конкретного проекта.
    """
    from app.services.status_mapping_service import StatusMappingService
    import asyncio
    
    try:
        token = get_token(instance_name, db, current_user.id)
        from app.jira.client import JiraClient
        
        jira_client = JiraClient(token.access_token, token.refresh_token)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            mappings = loop.run_until_complete(
                StatusMappingService.sync_project_statuses(
                    db=db,
                    project_key=project_key,
                    jira_client=jira_client,
                    synced_by_account_id=token.provider_user_id
                )
            )
        finally:
            loop.close()
        
        return {
            "success": True,
            "message": f"Synced {len(mappings)} statuses for project {project_key}",
            "statuses": [
                {
                    "name": m.status_name,
                    "is_open": m.is_open,
                    "is_in_progress": m.is_in_progress,
                    "is_closed": m.is_closed
                }
                for m in mappings
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.get("/project-statuses/{project_key}")
async def get_project_statuses_endpoint(
    project_key: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Возвращает статусы проекта из БД.
    """
    sync_service = JiraSyncService(db)
    statuses = sync_service.get_project_statuses(project_key)
    
    return {
        "success": True,
        "project_key": project_key,
        "statuses": statuses
    }


# ================= SYNC ISSUES TO DB =================

@router.post("/sync/{project_key}")
def sync_issues(
    project_key: str,
    instance_name: str = Query(...),
    sync_statuses_first: bool = Query(True, description="Сначала синхронизировать статусы"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Принудительная синхронизация задач проекта в БД.
    """
    try:
        sync_service = JiraSyncService(db)
        
        # Если нужно, сначала синхронизируем статусы
        if sync_statuses_first:
            token = get_token(instance_name, db, current_user.id)
            sync_service._sync_project_statuses_if_needed(project_key, token)
        
        result = sync_service.sync_project_issues(
            user_id=current_user.id,
            instance_name=instance_name,
            project_key=project_key
        )
        return {
            "success": True,
            "message": f"Synced {result['total']} issues",
            "details": result
        }
    except Exception as e:
        raise HTTPException(500, detail=f"Sync failed: {str(e)}")


@router.post("/sync-async/{project_key}")
async def sync_issues_async(
    project_key: Optional[str] = None,
    instance_name: str = Query(...),
    sync_statuses_first: bool = Query(True, description="Сначала синхронизировать статусы"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Асинхронная синхронизация задач проекта в БД через очередь.
    
    Если project_key не указан — синхронизируются ВСЕ проекты пользователя.
    Возвращает job_id для отслеживания статуса.
    """
    try:
        # Добавляем задачу в очередь
        job = sync_jira_queue.enqueue(
            sync_jira_task,
            args=(current_user.id, instance_name, project_key, sync_statuses_first),
            job_timeout="900s",  # 15 минут
            result_ttl=3600,
            failure_ttl=3600
        )
        
        message = "Sync for all projects queued" if not project_key else f"Sync for project {project_key} queued"
        
        return {
            "success": True,
            "message": message,
            "data": {
                "job_id": job.id,
                "status": "queued",
                "project_key": project_key,
                "instance_name": instance_name,
                "sync_statuses_first": sync_statuses_first
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to queue sync: {str(e)}")


@router.post("/sync-all-async")
async def sync_all_projects_async(
    instance_name: str = Query(...),
    sync_statuses_first: bool = Query(True, description="Сначала синхронизировать статусы"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Асинхронная синхронизация ВСЕХ проектов пользователя.
    """
    try:
        job = sync_jira_queue.enqueue(
            sync_jira_task,
            args=(current_user.id, instance_name, None, sync_statuses_first),
            job_timeout="900s",
            result_ttl=3600,
            failure_ttl=3600
        )
        
        return {
            "success": True,
            "message": "Sync for all projects queued",
            "data": {
                "job_id": job.id,
                "status": "queued",
                "instance_name": instance_name,
                "sync_statuses_first": sync_statuses_first
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to queue sync: {str(e)}")