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
from app.services.jira_sync_service import JiraSyncService
from app.services.github_sync_service import GithubSyncService
from app.services.project_sync_service import sync_projects_from_jira

logger = logging.getLogger(__name__)


def sync_jira_task(user_id: int, instance_name: str, project_key: str = None, sync_statuses_first: bool = True, full_sync: bool = False) -> dict:
    """
    Фоновая задача для синхронизации Jira проектов.

    Args:
        user_id: ID пользователя
        instance_name: Имя инстанса Jira
        project_key: Ключ проекта (если None — синхронизирует ВСЕ проекты пользователя)
        sync_statuses_first: Синхронизировать ли статусы проектов перед задачами
        full_sync: Полная синхронизация (True) или инкрементальная (False)
    """
    logger.info(f"Starting Jira sync for user {user_id}, instance {instance_name}")
    logger.info(f"Full sync: {full_sync}")
    if project_key:
        logger.info(f"Project filter: {project_key}")
    logger.info(f"Sync statuses first: {sync_statuses_first}")

    db = SessionLocal()
    try:
        # 1. Синхронизируем проекты (и статусы, если нужно)
        sync_result = sync_projects_from_jira(
            db=db,
            user_id=user_id,
            instance_name=instance_name,
            sync_statuses=sync_statuses_first
        )
        logger.info(f"Projects sync result: {sync_result}")

        # Получаем токен
        token = db.query(IntegrationToken).filter(
            IntegrationToken.user_id == user_id,
            IntegrationToken.instance_name == instance_name,
            IntegrationToken.provider == "jira"
        ).first()

        if not token:
            raise ValueError(f"Token not found for site {instance_name}")

        # Определяем список проектов для синхронизации задач
        if project_key:
            project_keys = [project_key]
        else:
            # Получаем проекты из Jira API для этого инстанса
            import requests
            projects_url = f"https://api.atlassian.com/ex/jira/{token.instance_id}/rest/api/3/project"
            headers = {"Authorization": f"Bearer {token.access_token}"}
            response = requests.get(projects_url, headers=headers, timeout=30)
            response.raise_for_status()
            jira_projects = response.json()
            jira_project_keys = [p["key"] for p in jira_projects]
            logger.info(f"Found {len(jira_project_keys)} projects from Jira API: {jira_project_keys}")
            
            # Фильтруем только те проекты, которые есть в БД у пользователя
            from app.db.models.core import Project, UserProject
            user_projects = db.query(Project).join(
                UserProject, UserProject.project_id == Project.id
            ).filter(
                UserProject.user_id == user_id,
                Project.is_active == True,
                Project.jira_project_key.in_(jira_project_keys)
            ).all()
            project_keys = [p.jira_project_key or p.key for p in user_projects]
            logger.info(f"Found {len(project_keys)} projects from DB matching Jira API: {project_keys}")

        # Синхронизируем задачи каждого проекта
        sync_service = JiraSyncService(db)

        total_result = {
            "projects_synced": sync_result,
            "issues": {
                "created": 0,
                "updated": 0,
                "total": 0,
                "projects": []
            }
        }

        for p_key in project_keys:
            try:
                logger.info(f"Syncing issues for project {p_key}...")
                
                # 🔥 ГЛАВНОЕ ИЗМЕНЕНИЕ: если full_sync=True или задач в БД нет — синхронизируем всё
                from app.db.models import JiraIssue
                # Проверяем, есть ли задачи в БД для этого проекта
                existing_issues_count = db.query(JiraIssue).filter(
                    JiraIssue.project_key == p_key,
                    JiraIssue.is_deleted == False
                ).count()

                if full_sync or existing_issues_count == 0:
                    # Полная синхронизация
                    jql_filter = f"project = {p_key}"
                else:
                    # Инкрементальная (только обновления за час)
                    jql_filter = f"project = {p_key} AND updated >= -1h"
                
                result = sync_service.sync_project_issues(
                    user_id=user_id,
                    instance_name=instance_name,
                    project_key=p_key,
                    jql=jql_filter,
                    sync_statuses=False
                )

                total_result["issues"]["created"] += result["created"]
                total_result["issues"]["updated"] += result["updated"]
                total_result["issues"]["total"] += result["total"]
                total_result["issues"]["projects"].append({
                    "project_key": p_key,
                    "details": result
                })

            except Exception as e:
                logger.error(f"Failed to sync issues for project {p_key}: {e}")
                total_result["issues"]["projects"].append({
                    "project_key": p_key,
                    "error": str(e)
                })

        db.commit()

        logger.info(f"Jira sync completed: {total_result}")
        return {
            "status": "completed",
            "instance_name": instance_name,
            "details": total_result,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Jira sync failed: {e}", exc_info=True)
        raise
    finally:
        db.close()


def sync_confluence_all_task(user_id: int, instance_name: str) -> dict:
    """Полная фоновая синхронизация всех Confluence project spaces."""
    logger.info(f"Starting full Confluence sync for user {user_id}, instance {instance_name}")

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

        spaces = asyncio.run(client.get_spaces(cloud_id=cloud_id, user_id=user_id))
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

                total_result["details"]["total_pages"] += result["pages_created"] + result["pages_updated"]
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
    """Фоновая задача для пересчёта метрик проекта."""
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


def sync_confluence_task(user_id: int, instance_name: str, space_id: str, space_key: str = None) -> dict:
    """Фоновая задача для синхронизации Confluence пространства."""
    logger.info(f"Starting Confluence sync for space {space_id}, user {user_id}")

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


def sync_github_task(user_id: int, instance_id: str, repo_full_name: str) -> dict:
    """Фоновая задача для синхронизации GitHub issues репозитория."""
    logger.info(f"Starting GitHub sync for repo {repo_full_name}, user {user_id}")

    try:
        db = SessionLocal()
        sync_service = GithubSyncService(db)
        
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        
        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    sync_service.sync_repo_issues_async(
                        user_id=user_id,
                        instance_id=instance_id,
                        repo_full_name=repo_full_name
                    )
                )
                result = future.result()
        else:
            result = asyncio.run(
                sync_service.sync_repo_issues_async(
                    user_id=user_id,
                    instance_id=instance_id,
                    repo_full_name=repo_full_name
                )
            )
        
        db.close()
        
        logger.info(f"GitHub sync completed for {repo_full_name}: {result}")
        
        return {
            "status": "completed",
            "repo_full_name": repo_full_name,
            "instance_id": instance_id,
            "details": result,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"GitHub sync failed for {repo_full_name}: {e}")
        raise


def sync_github_all_repos_task(user_id: int, instance_id: str) -> dict:
    """Фоновая задача для синхронизации всех репозиториев GitHub."""
    logger.info(f"Starting GitHub sync for all repos of {instance_id}, user {user_id}")
    
    try:
        db = SessionLocal()
        sync_service = GithubSyncService(db)
        
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        
        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    sync_service.sync_user_repos_issues(
                        user_id=user_id,
                        instance_id=instance_id
                    )
                )
                result = future.result()
        else:
            result = asyncio.run(
                sync_service.sync_user_repos_issues(
                    user_id=user_id,
                    instance_id=instance_id
                )
            )
        
        db.close()
        
        logger.info(f"GitHub sync completed for {instance_id}: {result}")
        
        return {
            "status": "completed",
            "instance_id": instance_id,
            "details": result,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"GitHub sync failed for {instance_id}: {e}")
        raise