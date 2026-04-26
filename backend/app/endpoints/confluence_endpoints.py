# app/endpoints/confluence_endpoints.py

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.db.session import get_db
from app.db.models import IntegrationToken
from app.core.dependencies import get_current_user
from app.services.token_service import TokenService
from app.confluence.client import ConfluenceClient
from app.workers.queues import sync_confluence_queue
from app.workers.tasks import sync_confluence_task

router = APIRouter()


def get_confluence_client(
    db: Session, 
    user_id: int, 
    instance_name: str
):
    """Возвращает ConfluenceClient для указанного сайта"""
    token = db.query(IntegrationToken).filter(
        IntegrationToken.user_id == user_id,
        IntegrationToken.instance_name == instance_name,
        IntegrationToken.provider == "jira"
    ).first()
    
    if not token:
        raise HTTPException(status_code=404, detail=f"Confluence site '{instance_name}' not found")
    
    token_service = TokenService(db)
    return ConfluenceClient(token_service), token.instance_id


@router.get("/spaces")
async def get_spaces(
    instance_name: str = Query(..., description="Имя сайта Confluence (например, newsitealf)"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Возвращает список пространств Confluence для указанного сайта"""
    client, cloud_id = get_confluence_client(db, current_user.id, instance_name)
    
    try:
        spaces = await client.get_spaces(cloud_id=cloud_id, user_id=current_user.id)
        return {
            "success": True,
            "data": [space.dict() for space in spaces]
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Confluence API error: {str(e)}")


@router.get("/pages")
async def get_pages(
    instance_name: str = Query(...),
    space_id: Optional[str] = Query(None),
    limit: int = Query(25, ge=1, le=100),
    start: int = Query(0, ge=0),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    client, cloud_id = get_confluence_client(db, current_user.id, instance_name)
    
    try:
        if space_id:
            data = await client._request(
                cloud_id=cloud_id,
                endpoint=f"/wiki/api/v2/spaces/{space_id}/pages",
                method="GET",
                params={"limit": limit, "start": start, "expand": "version,space"},
                user_id=current_user.id
            )
        else:
            data = await client._request(
                cloud_id=cloud_id,
                endpoint="/wiki/api/v2/pages",
                method="GET",
                params={"limit": limit, "start": start, "expand": "version,space"},
                user_id=current_user.id
            )
        
        results = data.get("results", [])
        has_next = len(results) == limit  # Если вернулось limit записей, вероятно есть ещё
        
        return {
            "success": True,
            "data": results,
            "meta": {
                "limit": limit,
                "start": start,
                "has_next": has_next,
                "next_start": start + limit if has_next else None
            }
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Confluence API error: {str(e)}")


@router.get("/pages/{page_id}/content")
async def get_page_content(
    page_id: str,
    instance_name: str = Query(...),
    format: str = Query("storage", regex="^(storage|view|export_view)$"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Возвращает содержимое страницы Confluence"""
    client, cloud_id = get_confluence_client(db, current_user.id, instance_name)
    
    try:
        content = await client.get_page_content(
            cloud_id=cloud_id,
            page_id=page_id,
            format=format,
            user_id=current_user.id
        )
        
        return {
            "success": True,
            "data": content
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Confluence API error: {str(e)}")



@router.post("/sync/{space_id}")
async def sync_confluence_pages(
    space_id: str,
    space_key: Optional[str] = Query(None),
    instance_name: str = Query(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Синхронизирует страницы из пространства Confluence в БД"""
    from app.services.confluence_sync_service import ConfluenceSyncService
    
    try:
        sync_service = ConfluenceSyncService(db)
        result = await sync_service.sync_space_pages(
            user_id=current_user.id,
            instance_name=instance_name,
            space_id=space_id,
            space_key=space_key
        )
        return {
            "success": True,
            "message": f"Synced {result['total']} pages",
            "details": result
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.post("/sync-async/{space_id}")
async def sync_confluence_async(
    space_id: str,
    space_key: Optional[str] = Query(None),
    instance_name: str = Query(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Асинхронная синхронизация страниц пространства Confluence в БД через очередь.
    Возвращает job_id для отслеживания статуса.
    """
    try:
        job = sync_confluence_queue.enqueue(
            sync_confluence_task,
            args=(current_user.id, instance_name, space_id, space_key),
            job_timeout="300s",
            result_ttl=3600,
            failure_ttl=3600
        )
        
        return {
            "success": True,
            "message": f"Sync for space {space_id} queued",
            "data": {
                "job_id": job.id,
                "status": "queued",
                "space_id": space_id,
                "instance_name": instance_name
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to queue sync: {str(e)}")