# app/workers/tasks.py

import logging
from datetime import datetime
from app.db.session import SessionLocal
from app.services.jira_sync_service import JiraSyncService

logger = logging.getLogger(__name__)


def sync_jira_task(user_id: int, instance_name: str, project_key: str) -> dict:
    """
    Фоновая задача для синхронизации Jira проектов.
    Выполняется в воркере.
    """
    logger.info(f"Starting Jira sync for project {project_key}, user {user_id}")
    
    try:
        # Создаём сессию БД (воркер синхронный)
        db = SessionLocal()
        sync_service = JiraSyncService(db)
        
        result = sync_service.sync_project_issues(
            user_id=user_id,
            instance_name=instance_name,
            project_key=project_key
        )
        
        db.close()
        
        logger.info(f"Jira sync completed for {project_key}: {result}")
        
        return {
            "status": "completed",
            "project_key": project_key,
            "instance_name": instance_name,
            "details": result,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Jira sync failed for {project_key}: {e}")
        raise

def sync_confluence_task(user_id: int, instance_name: str, space_id: str, space_key: str = None) -> dict:
    """
    Фоновая задача для синхронизации Confluence пространства.
    Выполняется в воркере.
    """
    import asyncio
    logger.info(f"Starting Confluence sync for space {space_id}, user {user_id}")
    
    try:
        db = SessionLocal()
        
        # Нужно запустить асинхронную функцию в синхронном контексте
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        from app.services.confluence_sync_service import ConfluenceSyncService
        sync_service = ConfluenceSyncService(db)
        
        result = loop.run_until_complete(
            sync_service.sync_space_pages(
                user_id=user_id,
                instance_name=instance_name,
                space_id=space_id,
                space_key=space_key
            )
        )
        
        loop.close()
        db.close()
        
        logger.info(f"Confluence sync completed for space {space_id}: {result}")
        
        return {
            "status": "completed",
            "space_id": space_id,
            "instance_name": instance_name,
            "details": result,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Confluence sync failed for space {space_id}: {e}")
        raise
