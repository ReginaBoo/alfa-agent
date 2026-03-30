from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import requests

from app.db.session import get_db
from app.db.models import AtlassianToken, User

router = APIRouter()


def get_current_user(db: Session = Depends(get_db)):
    """Получаем первого пользователя из БД (временное решение)"""
    user = db.query(User).first()
    if not user:
        raise HTTPException(status_code=401, detail="No user found. Please authenticate first.")
    return user


def get_current_token(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получаем токен для текущего пользователя"""
    token = db.query(AtlassianToken).filter(
        AtlassianToken.user_id == current_user.id
    ).first()
    
    if not token:
        raise HTTPException(
            status_code=401, 
            detail="No token found for user. Please authenticate with Jira first."
        )
    return token


@router.get("/sites")
def get_sites(
    token = Depends(get_current_token),
    db: Session = Depends(get_db)
):
    """Получить список всех доступных сайтов"""
    try:
        resources_response = requests.get(
            "https://api.atlassian.com/oauth/token/accessible-resources",
            headers={"Authorization": f"Bearer {token.access_token}"},
            timeout=10
        )
        resources_response.raise_for_status()
        resources = resources_response.json()
        
        # Получаем токены из БД для этого пользователя
        db_tokens = db.query(AtlassianToken).filter(
            AtlassianToken.user_id == token.user_id
        ).all()
        
        # Обогащаем информацию о сайтах
        sites = []
        for resource in resources:
            db_token = next((t for t in db_tokens if t.cloud_id == resource["id"]), None)
            sites.append({
                "cloud_id": resource["id"],
                "name": resource.get("name"),
                "url": resource.get("url"),
                "scopes": resource.get("scopes", []),
                "has_token": db_token is not None,
                "token_created_at": db_token.created_at.isoformat() if db_token and db_token.created_at else None
            })
        
        return {
            "success": True,
            "sites": sites
        }
        
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Atlassian API error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.get("/projects")
def get_projects(
    site_name: str = Query(None, description="Site name (e.g., reginaboo, newtestsit)"),
    token = Depends(get_current_token),
    db: Session = Depends(get_db)
):
    """Получить проекты Jira для указанного сайта"""
    try:
        # Получаем все доступные ресурсы
        resources_response = requests.get(
            "https://api.atlassian.com/oauth/token/accessible-resources",
            headers={"Authorization": f"Bearer {token.access_token}"},
            timeout=10
        )
        resources_response.raise_for_status()
        resources = resources_response.json()
        
        if not resources:
            raise HTTPException(status_code=404, detail="No accessible resources found")
        
        # Выбираем сайт
        if site_name:
            selected_resource = None
            for resource in resources:
                if resource.get("name") == site_name:
                    selected_resource = resource
                    break
            
            if not selected_resource:
                raise HTTPException(
                    status_code=404, 
                    detail=f"Site '{site_name}' not found. Available sites: {[r.get('name') for r in resources]}"
                )
        else:
            selected_resource = resources[0]
        
        cloud_id = selected_resource["id"]
        site_url = selected_resource["url"]
        site_name_display = selected_resource.get("name")
        
        # Получаем проекты из Jira
        projects_response = requests.get(
            f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3/project",
            headers={"Authorization": f"Bearer {token.access_token}"},
            timeout=10
        )
        projects_response.raise_for_status()
        projects = projects_response.json()
        
        return {
            "success": True,
            "site": {
                "cloud_id": cloud_id,
                "url": site_url,
                "name": site_name_display
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