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




def calculate_metrics_task(user_id: int, project_key: str) -> dict:
    """
    Фоновая задача для пересчёта метрик проекта.
    Выполняется в воркере.
    """
    logger.info(f"Starting metrics calculation for project {project_key}, user {user_id}")
    
    try:
        db = SessionLocal()
        
        from app.services.metrics.workload_index import calculate_workload_index
        from app.services.metrics.sla_score import calculate_sla_score
        from app.services.metrics.health_score import calculate_health_score, save_health_score
        from app.db.models import JiraIssue
        
        # Находим assignee_id (исполнителя) для проекта
        assignee = db.query(JiraIssue.assignee_account_id).filter(
            JiraIssue.project_key == project_key,
            JiraIssue.assignee_account_id.isnot(None)
        ).first()
        
        if not assignee:
            logger.warning(f"No assignee found for project {project_key}")
            return {
                "status": "skipped",
                "project_key": project_key,
                "reason": "No assignee found"
            }
        
        assignee_id = assignee[0]
        
        # 1. Workload Index
        wi = calculate_workload_index(
            db=db,
            assignee_account_id=assignee_id,
            project_key=project_key,
            weeks=2
        )
        logger.info(f"WI for {project_key}: {wi}")
        
        # 2. SLA Score
        sla_result = calculate_sla_score(db, project_key=project_key)
        logger.info(f"SLA for {project_key}: {sla_result['sla_score']}%")
        
        # 3. Health Score
        health = calculate_health_score(db, project_key=project_key)
        logger.info(f"Health for {project_key}: {health['health_score']}")
        
        # 4. Сохраняем Health Score в project_health
        save_health_score(db, project_key, health)
        
        db.close()
        
        return {
            "status": "completed",
            "project_key": project_key,
            "workload_index": wi,
            "sla_score": sla_result['sla_score'],
            "health_score": health['health_score'],
            "health_status": health['status_text'],
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Metrics calculation failed for {project_key}: {e}")
        raise


