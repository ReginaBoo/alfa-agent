# app/workers/tasks.py

import asyncio
import logging
from datetime import datetime
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models import IntegrationToken
from app.confluence.client import ConfluenceClient
from app.services.token_service import TokenService
from app.services.confluence_sync_service import ConfluenceSyncService

logger = logging.getLogger(__name__)


def sync_jira_task(user_id: int, instance_name: str, project_key: str = None) -> dict:
    """
    Фоновая задача для синхронизации Jira проектов.

    Если project_key не указан — синхронизирует ВСЕ проекты пользователя.
    """
    logger.info(
        f"Starting Jira sync for user {user_id}, instance {instance_name}")
    if project_key:
        logger.info(f"Project filter: {project_key}")

    try:
        db = SessionLocal()

        # Получаем токен
        token = db.query(IntegrationToken).filter(
            IntegrationToken.user_id == user_id,
            IntegrationToken.instance_name == instance_name,
            IntegrationToken.provider == "jira"
        ).first()

        if not token:
            raise ValueError(f"Token not found for site {instance_name}")

        # Получаем список проектов (если project_key не указан)
        if not project_key:
            import requests
            projects_url = f"https://api.atlassian.com/ex/jira/{token.instance_id}/rest/api/3/project"
            headers = {"Authorization": f"Bearer {token.access_token}"}
            response = requests.get(projects_url, headers=headers, timeout=30)
            response.raise_for_status()
            projects = response.json()
            project_keys = [p["key"] for p in projects]
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
        from app.services.project_sync_service import sync_projects_from_jira
        try:
            sync_result = sync_projects_from_jira(
                db=db,
                user_id=user_id,
                instance_name=instance_name
            )
            logger.info(f"Projects synced: {sync_result}")
        except Exception as e:
            logger.error(f"Failed to sync projects: {e}")
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

            except Exception as e:
                logger.error(f"Failed to sync project {p_key}: {e}")
                total_result["projects_synced"].append({
                    "project_key": p_key,
                    "error": str(e)
                })

        db.commit()
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


def sync_confluence_all_task(user_id: int, instance_name: str) -> dict:
    """
    Полная фоновая синхронизация всех Confluence project spaces.
    """
    logger.info(
        f"Starting full Confluence sync for user {user_id}, instance {instance_name}")

    total_result = {
        "status": "completed",
        "instance_name": instance_name,
        "details": {
            "spaces_synced": [],
            "total_pages": 0,
            "total_versions": 0,
            "total_comments": 0,
            "total_errors": 0
        },
        "timestamp": datetime.utcnow().isoformat()
    }

    db = SessionLocal()

    try:
        token = db.query(IntegrationToken).filter(
            IntegrationToken.user_id == user_id,
            IntegrationToken.instance_name == instance_name,
            IntegrationToken.provider == "jira"
        ).first()

        if not token:
            raise ValueError(f"Token not found for site {instance_name}")

        token_service = TokenService(db)
        client = ConfluenceClient(token_service)
        sync_service = ConfluenceSyncService(db)
        cloud_id = token.instance_id

        spaces = asyncio.run(client.get_spaces(
            cloud_id=cloud_id, user_id=user_id))
        logger.info(f"Found {len(spaces)} total spaces")

        # получаем Jira project keys
        import requests
        jira_projects_resp = requests.get(
            f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3/project",
            headers={"Authorization": f"Bearer {token.access_token}"},
            timeout=30
        )
        jira_projects_resp.raise_for_status()
        jira_projects = jira_projects_resp.json()
        jira_project_keys = {p["key"] for p in jira_projects}

        logger.info(f"Jira linked project keys: {jira_project_keys}")

        # только project-linked spaces
        project_spaces = [
            s for s in spaces
            if not s.key.startswith("~") and s.key in jira_project_keys
        ]

        logger.info(f"Filtered to {len(project_spaces)} project-linked spaces")

        for space in project_spaces:
            try:
                result = asyncio.run(
                    sync_service.sync_space_pages(
                        user_id=user_id,
                        instance_name=instance_name,
                        space_id=space.id,
                        space_key=space.key
                    )
                )

                total_result["details"]["total_pages"] += result["pages_created"] + \
                    result["pages_updated"]
                total_result["details"]["total_versions"] += result["versions_saved"]
                total_result["details"]["total_comments"] += result["comments_saved"]
                total_result["details"]["total_errors"] += result["errors"]

                total_result["details"]["spaces_synced"].append({
                    "space_id": space.id,
                    "space_key": space.key,
                    "name": space.name,
                    "pages": result["pages_created"] + result["pages_updated"],
                    "versions": result["versions_saved"],
                    "comments": result["comments_saved"]
                })

            except Exception as e:
                logger.error(f"Failed to sync space {space.id}: {e}")
                total_result["details"]["total_errors"] += 1

        db.commit()

    except Exception as e:
        db.rollback()
        logger.error(f"Confluence sync failed: {e}")
        raise
    finally:
        db.close()

    return total_result


def calculate_metrics_task(user_id: int, project_key: str) -> dict:
    """
    Фоновая задача для пересчёта метрик проекта.
    Выполняется в воркере.
    """
    logger.info(
        f"Starting metrics calculation for project {project_key}, user {user_id}")

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


def sync_confluence_task(user_id: int, instance_name: str, space_id: str, space_key: str = None) -> dict:
    """
    Фоновая задача для синхронизации Confluence пространства.
    Выполняется в воркере.
    """
    import asyncio
    logger.info(
        f"Starting Confluence sync for space {space_id}, user {user_id}")

    try:
        db = SessionLocal()
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

        logger.info(
            f"Confluence sync completed for space {space_id}: {result}")

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

def calculate_project_health_task(user_id: int, project_key: str, period_days: int = 30) -> dict:
    """
    Фоновая задача: расчёт и сохранение Project Health Score.
    """
    logger.info(f"Starting Health Score calculation for {project_key}")
    
    try:
        db = SessionLocal()
        
        from app.services.metrics.health_score import calculate_health_score, save_health_score
        
        health_data = calculate_health_score(db, project_key, period_days)
        saved = save_health_score(db, project_key, health_data, period_days)
        
        db.close()
        
        if not saved:
            return {
                "status": "failed",
                "project_key": project_key,
                "error": f"Project '{project_key}' not found"
            }
        
        return {
            "status": "completed",
            "project_key": project_key,
            "health_score": health_data['health_score'],
            "status_label": health_data['status_text'],
            "components": health_data['components'],
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Health Score calculation failed for {project_key}: {e}")
        raise

def calculate_doc_health_task(user_id: int, project_key: str, period_days: int = 30) -> dict:
    """
    Фоновая задача: расчёт Documentation Health Score.
    """
    logger.info(f"Starting DHS calculation for {project_key}")
    
    try:
        db = SessionLocal()
        
        from app.services.metrics.doc_health_score import calculate_doc_health_score, save_doc_health_score
        
        dhs_data = calculate_doc_health_score(db, project_key, period_days)
        saved = save_doc_health_score(db, project_key, dhs_data, period_days)
        
        db.close()
        
        if not saved:
            return {
                "status": "failed",
                "project_key": project_key,
                "error": f"Project '{project_key}' not found"
            }
        
        return {
            "status": "completed",
            "project_key": project_key,
            "dhs_score": dhs_data['dhs_score'],
            "status_label": dhs_data['status_text'],
            "components": dhs_data['components'],
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"DHS calculation failed for {project_key}: {e}")
        raise