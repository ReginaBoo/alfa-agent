# app/endpoints/jira_endpoints.py

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

router = APIRouter()


# ================= HELPERS =================

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
        for attempt in range(2):  # Максимум 2 попытки
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_data
            )
            
            if response.status_code == 401 and attempt == 0:
                # Обновляем токен
                from app.services.token_refresh_service import TokenRefreshService
                TokenRefreshService.update_user_tokens(db, user_id)
                # Получаем новый токен
                token = get_token_by_instance_id(token.instance_id, db, user_id)
                headers["Authorization"] = f"Bearer {token.access_token}"
                continue
            
            response.raise_for_status()
            return response.json()
        
        raise HTTPException(401, "Token refresh failed")


# ================= PROJECTS (асинхронно) =================

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


# ================= ISSUES (с Story Points) =================

@router.get("/issues")
async def search_issues(
    instance_name: str = Query(...),
    jql: str = Query(...),
    start_at: int = Query(0, ge=0),
    max_results: int = Query(50, ge=1, le=100),
    fields: Optional[str] = Query("*all"),  # По умолчанию все поля
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    token = get_token(instance_name, db, current_user.id)
    
    params = {
        "jql": jql,
        "startAt": start_at,
        "maxResults": max_results,
        "fields": fields  # Включает Story Points
    }
    
    try:
        data = await _make_jira_request(
            token=token,
            path="search",
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