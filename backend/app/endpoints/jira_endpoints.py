# app/endpoints/jira_endpoints.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import requests

from app.db.session import get_db
from app.db.models import AtlassianToken
from app.core.dependencies import get_current_user, get_valid_token

router = APIRouter()


@router.get("/sites")
def get_sites(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получить список всех авторизованных сайтов"""
    tokens = db.query(AtlassianToken).filter(
        AtlassianToken.user_id == current_user.id
    ).all()
    
    return {
        "success": True,
        "sites": [
            {
                "cloud_id": t.cloud_id,
                "site_name": t.site_name,
                "site_url": t.site_url,
                "expires_at": t.expires_at.isoformat() if t.expires_at else None
            }
            for t in tokens
        ]
    }


@router.get("/projects")
def get_projects(
    site_name: str = Query(..., description="Site name"),
    token: AtlassianToken = Depends(get_valid_token),
    db: Session = Depends(get_db)
):
    """Получить проекты Jira для указанного сайта"""
    try:
        projects_response = requests.get(
            f"https://api.atlassian.com/ex/jira/{token.cloud_id}/rest/api/3/project",
            headers={"Authorization": f"Bearer {token.access_token}"},
            timeout=10
        )
        projects_response.raise_for_status()
        projects = projects_response.json()
        
        return {
            "success": True,
            "site": {
                "cloud_id": token.cloud_id,
                "url": token.site_url,
                "name": token.site_name
            },
            "total_projects": len(projects),
            "projects": [
                {
                    "id": p.get("id"),
                    "key": p.get("key"),
                    "name": p.get("name"),
                    "url": p.get("self")
                }
                for p in projects
            ]
        }
        
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Atlassian API error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")