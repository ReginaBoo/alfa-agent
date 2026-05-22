"""
Сервис для синхронизации проектов из Jira в БД
"""

import logging
from datetime import datetime
from sqlalchemy.orm import Session
from app.db.models.core import Project, UserProject
from app.db.models import IntegrationToken
from app.db.models.normalized import ProjectStatusMapping
import requests
import asyncio

logger = logging.getLogger(__name__)


def _make_jira_request_with_refresh(
    url: str,
    token: IntegrationToken,
    db: Session,
    user_id: int,
    method: str = "GET",
    timeout: int = 30
) -> requests.Response:
    """
    Выполняет запрос к Jira API с автоматическим обновлением токена при 401
    """
    from app.services.token_refresh_service import TokenRefreshService
    
    headers = {"Authorization": f"Bearer {token.access_token}"}
    
    for attempt in range(2):
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            timeout=timeout
        )
        
        if response.status_code == 401 and attempt == 0:
            logger.info(f"Token expired, refreshing for user {user_id}")
            TokenRefreshService.update_user_tokens(db, user_id)
            
            # Обновляем токен в БД
            db.refresh(token)
            headers["Authorization"] = f"Bearer {token.access_token}"
            continue
        
        return response
    
    return response


def sync_projects_from_jira(
    db: Session,
    user_id: int,
    instance_name: str,
    token_instance_id: str = None,
    token_access_token: str = None,
    sync_statuses: bool = True
) -> dict:
    """
    Синхронизирует проекты из Jira в таблицу core.projects
    """
    
    # Получаем токен, если не передан
    if not token_instance_id or not token_access_token:
        token = db.query(IntegrationToken).filter(
            IntegrationToken.user_id == user_id,
            IntegrationToken.instance_name == instance_name,
            IntegrationToken.provider == "jira"
        ).first()
        
        if not token:
            raise ValueError(f"Token not found for site {instance_name}")
        
        cloud_id = token.instance_id
        provider_user_id = token.provider_user_id
    else:
        # Создаём временный объект токена для передачи
        token = IntegrationToken(
            instance_id=token_instance_id,
            access_token=token_access_token,
            user_id=user_id
        )
        cloud_id = token_instance_id
        provider_user_id = None
    
    # Запрашиваем проекты из Jira API с автообновлением
    url = f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3/project"
    
    response = _make_jira_request_with_refresh(url, token, db, user_id)
    response.raise_for_status()
    
    jira_projects = response.json()
    
    created_count = 0
    updated_count = 0
    statuses_synced = 0
    
    # ========== 1. СОХРАНЯЕМ ПРОЕКТЫ ==========
    for jp in jira_projects:
        project_key = jp['key']
        
        # Проверяем, существует ли проект в нашей БД
        existing = db.query(Project).filter(Project.key == project_key).first()
        jira_ui_url = f"https://{instance_name}.atlassian.net/jira/software/projects/{project_key}"
        
        project_data = {
            'key': project_key,
            'name': jp['name'],
            'jira_project_key': project_key,
            'url': jira_ui_url,
            'avatar_url': jp.get('avatarUrls', {}).get('48x48'),
            'category': jp.get('projectTypeKey'),
            'description': jp.get('description', ''),
            'is_active': jp.get('isPrivate') == False,
        }
        
        if existing:
            existing.name = project_data['name']
            existing.url = project_data['url']
            existing.avatar_url = project_data['avatar_url']
            existing.category = project_data['category']
            existing.description = project_data['description']
            existing.is_active = project_data['is_active']
            updated_count += 1
        else:
            project = Project(**project_data)
            db.add(project)
            db.flush()
            
            user_project = UserProject(
                user_id=user_id,
                project_id=project.id,
                role='owner'
            )
            db.add(user_project)
            created_count += 1
    
    # ========== КОММИТИМ ПРОЕКТЫ ДО СТАТУСОВ ==========
    db.commit()
    logger.info(f"Projects saved: {created_count} created, {updated_count} updated")
    
    # ========== 2. СИНХРОНИЗИРУЕМ СТАТУСЫ (БЕЗ JiraClient) ==========
    if sync_statuses:
        # Получаем список ключей проектов
        project_keys_to_sync = [p['key'] for p in jira_projects]
        
        # Удаляем старые статусы для этих проектов
        deleted_count = db.query(ProjectStatusMapping).filter(
            ProjectStatusMapping.project_key.in_(project_keys_to_sync)
        ).delete(synchronize_session=False)
        logger.info(f"Deleted {deleted_count} old status mappings")
        
        # Синхронизируем статусы для каждого проекта напрямую
        for project_key in project_keys_to_sync:
            try:
                statuses_url = f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3/project/{project_key}/statuses"
                statuses_response = _make_jira_request_with_refresh(statuses_url, token, db, user_id)
                
                if statuses_response.status_code == 200:
                    statuses_data = statuses_response.json()
                    
                    # ДЕДУПЛИКАЦИЯ: собираем уникальные статусы
                    unique_statuses = {}
                    for issue_type_data in statuses_data:
                        for status in issue_type_data.get("statuses", []):
                            status_name = status.get("name")
                            if status_name not in unique_statuses:
                                unique_statuses[status_name] = status
                    
                    # Сохраняем только уникальные статусы
                    for status_name, status in unique_statuses.items():
                        status_category = status.get("statusCategory", {})
                        category_key = status_category.get("key", "").lower()
                        
                        # Универсальная обработка категорий
                        if category_key == "new":
                            is_open = True
                            is_in_progress = False
                            is_closed = False
                        elif category_key == "indeterminate":
                            is_open = True
                            is_in_progress = True
                            is_closed = False
                        elif category_key == "done":
                            is_open = False
                            is_in_progress = False
                            is_closed = True
                        elif category_key in ["undefined", "", None]:
                            # Если категория не определена, используем эвристику по имени
                            status_lower = status_name.lower()
                            closed_keywords = ['done', 'closed', 'resolved', 'completed', 'finished', 'готово', 'выполнено']
                            if any(kw in status_lower for kw in closed_keywords):
                                is_open = False
                                is_in_progress = False
                                is_closed = True
                            elif any(kw in status_lower for kw in ['progress', 'review', 'работе', 'тестирование']):
                                is_open = True
                                is_in_progress = True
                                is_closed = False
                            else:
                                is_open = True
                                is_in_progress = False
                                is_closed = False
                            logger.info(f"Status '{status_name}' (category='{category_key}') classified by name heuristic")
                        else:
                            # Неизвестная категория
                            logger.warning(f"Unknown category '{category_key}' for status '{status_name}', using open status as fallback")
                            is_open = True
                            is_in_progress = False
                            is_closed = False
                        
                        new_mapping = ProjectStatusMapping(
                            project_key=project_key,
                            status_name=status_name,
                            is_open=is_open,
                            is_in_progress=is_in_progress,
                            is_closed=is_closed,
                            jira_category=category_key,
                            last_synced_at=datetime.utcnow(),
                            synced_by_account_id=provider_user_id
                        )
                        db.add(new_mapping)
                        statuses_synced += 1
                    
                    db.commit()
                    logger.info(f"Synced {len(unique_statuses)} statuses for {project_key}")
                else:
                    logger.error(f"Failed to get statuses for {project_key}: {statuses_response.status_code}")
            except Exception as e:
                logger.error(f"Failed to sync statuses for {project_key}: {e}")
                db.rollback()
                # Продолжаем со следующим проектом
        
        db.commit()
    
    logger.info(f"Sync completed: projects created={created_count}, updated={updated_count}, "
                f"statuses synced={statuses_synced}")
    
    return {
        'created': created_count,
        'updated': updated_count,
        'total': created_count + updated_count,
        'statuses_synced': statuses_synced
    }


def get_user_projects_with_metrics(
    db: Session,
    user_id: int
) -> list:
    """Возвращает список проектов пользователя с агрегированными метриками"""
    projects = db.query(Project).join(
        UserProject, UserProject.project_id == Project.id
    ).filter(
        UserProject.user_id == user_id,
        Project.is_active == True
    ).all()
    
    result = []
    for project in projects:
        statuses = db.query(ProjectStatusMapping).filter(
            ProjectStatusMapping.project_key == project.key
        ).all()
        
        result.append({
            'id': project.id,
            'key': project.key,
            'name': project.name,
            'category': project.category,
            'avatar_url': project.avatar_url,
            'statuses': [
                {
                    'name': s.status_name,
                    'is_open': s.is_open,
                    'is_in_progress': s.is_in_progress,
                    'is_closed': s.is_closed
                }
                for s in statuses
            ],
            'last_synced_at': project.last_synced_at.isoformat() if project.last_synced_at else None
        })
    
    return result


def refresh_all_project_statuses(
    db: Session,
    user_id: int,
    instance_name: str
) -> dict:
    """Принудительно обновляет статусы для всех проектов пользователя"""
    token = db.query(IntegrationToken).filter(
        IntegrationToken.user_id == user_id,
        IntegrationToken.instance_name == instance_name,
        IntegrationToken.provider == "jira"
    ).first()
    
    if not token:
        raise ValueError(f"Token not found for site {instance_name}")
    
    cloud_id = token.instance_id
    provider_user_id = token.provider_user_id
    
    projects = db.query(Project).join(
        UserProject, UserProject.project_id == Project.id
    ).filter(
        UserProject.user_id == user_id
    ).all()
    
    statuses_updated = 0
    
    for project in projects:
        try:
            statuses_url = f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3/project/{project.key}/statuses"
            
            response = _make_jira_request_with_refresh(statuses_url, token, db, user_id)
            
            if response.status_code == 200:
                statuses_data = response.json()
                
                # Дедупликация статусов
                unique_statuses = {}
                for issue_type_data in statuses_data:
                    for status in issue_type_data.get("statuses", []):
                        status_name = status.get("name")
                        if status_name not in unique_statuses:
                            unique_statuses[status_name] = status
                
                for status_name, status in unique_statuses.items():
                    status_category = status.get("statusCategory", {})
                    category_key = status_category.get("key")
                    
                    is_open = category_key in ["todo", "in-progress"]
                    is_in_progress = category_key == "in-progress"
                    is_closed = category_key == "done"
                    
                    existing = db.query(ProjectStatusMapping).filter(
                        ProjectStatusMapping.project_key == project.key,
                        ProjectStatusMapping.status_name == status_name
                    ).first()
                    
                    if existing:
                        existing.is_open = is_open
                        existing.is_in_progress = is_in_progress
                        existing.is_closed = is_closed
                        existing.jira_category = category_key
                        existing.last_synced_at = datetime.utcnow()
                        existing.synced_by_account_id = provider_user_id
                    else:
                        new_mapping = ProjectStatusMapping(
                            project_key=project.key,
                            status_name=status_name,
                            is_open=is_open,
                            is_in_progress=is_in_progress,
                            is_closed=is_closed,
                            jira_category=category_key,
                            last_synced_at=datetime.utcnow(),
                            synced_by_account_id=provider_user_id
                        )
                        db.add(new_mapping)
                    statuses_updated += 1
                
                db.commit()
                logger.info(f"Refreshed statuses for {project.key}")
            else:
                logger.error(f"Failed to get statuses for {project.key}: {response.status_code}")
        except Exception as e:
            logger.error(f"Failed to refresh statuses for {project.key}: {e}")
            db.rollback()
    
    return {
        'projects_processed': len(projects),
        'statuses_updated': statuses_updated
    }