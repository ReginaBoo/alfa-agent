# app/endpoints/jira_endpoints.py

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import IntegrationToken
from app.core.dependencies import get_current_user
from app.workers.queues import sync_jira_queue
from app.workers.tasks import sync_jira_task

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
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    token = get_token(instance_name, db, current_user.id)
    
    try:
        data = await _make_jira_request(
            token=token,
            path="project",
            db=db,
            user_id=current_user.id
        )
        
        return {
            "success": True,
            "total_projects": len(data),
            "projects": [
                {"id": p.get("id"), "key": p.get("key"), "name": p.get("name")}
                for p in data
            ]
        }
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"Jira API error: {str(e)}")


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
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    token = get_token(instance_name, db, current_user.id)
    
    try:
        data = await _make_jira_request(
            token=token,
            path=f"issue/{issue_key}/changelog",
            db=db,
            user_id=current_user.id
        )
        
        return {
            "success": True,
            "changelog": data
        }
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"Jira API error: {str(e)}")


# ================= SYNC ISSUES TO DB =================

@router.post("/sync/{project_key}")
def sync_issues(
    project_key: str,
    instance_name: str = Query(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Принудительная синхронизация задач проекта в БД"""
    from app.services.jira_sync_service import JiraSyncService
    try:
        sync_service = JiraSyncService(db)
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
        raise HTTPException(500, f"Sync failed: {str(e)}")



@router.post("/sync-async/{project_key}")
async def sync_issues_async(
    project_key: str,
    instance_name: str = Query(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Асинхронная синхронизация задач проекта в БД через очередь.
    Возвращает job_id для отслеживания статуса.
    """
    try:
        # Добавляем задачу в очередь
        job = sync_jira_queue.enqueue(
            sync_jira_task,
            args=(current_user.id, instance_name, project_key),
            job_timeout="300s",  # 5 минут на выполнение
            result_ttl=3600,      # результат хранится час
            failure_ttl=3600      # ошибки тоже хранятся час
        )
        
        return {
            "success": True,
            "message": f"Sync for project {project_key} queued",
            "data": {
                "job_id": job.id,
                "status": "queued",
                "project_key": project_key,
                "instance_name": instance_name
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to queue sync: {str(e)}")