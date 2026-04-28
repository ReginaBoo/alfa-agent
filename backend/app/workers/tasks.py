# app/workers/tasks.py

import logging
from datetime import datetime
from app.db.session import SessionLocal
from app.services.jira_sync_service import JiraSyncService
import asyncio

logger = logging.getLogger(__name__)


def sync_jira_task(user_id: int, instance_name: str, project_key: str = None) -> dict:
    """
    Фоновая задача для синхронизации Jira проектов.
    
    Если project_key не указан — синхронизирует ВСЕ проекты пользователя.
    Выполняется в воркере.
    """
    logger.info(f"Starting Jira sync for user {user_id}, instance {instance_name}")
    if project_key:
        logger.info(f"Project filter: {project_key}")
    
    try:
        db = SessionLocal()
        
        # Получаем токен для доступа к API
        from app.db.models import IntegrationToken
        token = db.query(IntegrationToken).filter(
            IntegrationToken.user_id == user_id,
            IntegrationToken.instance_name == instance_name,
            IntegrationToken.provider == "jira"
        ).first()
        
        if not token:
            raise ValueError(f"Token not found for site {instance_name}")
        
        # Получаем список всех проектов
        from app.jira.client import JiraClient
        from app.services.token_service import TokenService
        
        token_service = TokenService(db)
        client = JiraClient(token_service)
        
        # Если project_key не указан — получаем все проекты
        if not project_key:
            projects = asyncio.run(client.get_projects(
                cloud_id=token.instance_id,
                user_id=user_id
            ))
            project_keys = [p.key for p in projects]
            logger.info(f"Found {len(project_keys)} projects: {project_keys}")
        else:
            project_keys = [project_key]
        
        # Синхронизируем каждый проект
        from app.services.jira_sync_service import JiraSyncService
        sync_service = JiraSyncService(db)
        
        total_result = {
            "created": 0,
            "updated": 0,
            "total": 0,
            "projects_synced": []
        }
        
        for p_key in project_keys:
            try:
                logger.info(f"Syncing project {p_key}...")
                result = sync_service.sync_project_issues(
                    user_id=user_id,
                    instance_name=instance_name,
                    project_key=p_key
                )
                
                total_result["created"] += result["created"]
                total_result["updated"] += result["updated"]
                total_result["total"] += result["total"]
                total_result["projects_synced"].append({
                    "project_key": p_key,
                    "details": result
                })
                
                logger.info(f"Project {p_key} synced: {result}")
                
            except Exception as e:
                logger.error(f"Failed to sync project {p_key}: {e}")
                total_result["projects_synced"].append({
                    "project_key": p_key,
                    "error": str(e)
                })
        
        db.close()
        
        logger.info(f"Jira sync completed: {total_result}")
        return {
            "status": "completed",
            "instance_name": instance_name,
            "details": total_result,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Jira sync failed: {e}")
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


