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
            logger.error(f"Token expired, refreshing for user {user_id}")
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
    logger.error(
        f"Projects from Jira API: "
        f"{[p['key'] for p in jira_projects]}"
    )
    created_count = 0
    updated_count = 0
    linked_count = 0  # НОВЫЙ счетчик для созданных связей
    statuses_synced = 0
    
    # ========== 1. СОХРАНЯЕМ ПРОЕКТЫ ==========
    for jp in jira_projects:
        project_key = jp['key']
        
        # Проверяем, существует ли проект в нашей БД
        existing_project = db.query(Project).filter(Project.key == project_key).first()
        
        # Проверяем, есть ли связь этого проекта с текущим пользователем
        existing_link = None
        if existing_project:
            existing_link = db.query(UserProject).filter(
                UserProject.user_id == user_id,
                UserProject.project_id == existing_project.id
            ).first()
        
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
        
        if not existing_project:
            # СЛУЧАЙ 1: Проекта нет в БД - создаем проект и связь
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
            logger.error(f"Created new project {project_key} with link to user {user_id}")
            
        elif not existing_link:
            # СЛУЧАЙ 2: Проект есть, но связи с пользователем нет - добавляем связь
            user_project = UserProject(
                user_id=user_id,
                project_id=existing_project.id,
                role='owner'
            )
            db.add(user_project)
            linked_count += 1
            
            # Обновляем информацию о проекте
            existing_project.name = project_data['name']
            existing_project.url = project_data['url']
            existing_project.avatar_url = project_data['avatar_url']
            existing_project.category = project_data['category']
            existing_project.description = project_data['description']
            existing_project.is_active = project_data['is_active']
            updated_count += 1
            logger.error(f"Added missing link for user {user_id} to existing project {project_key}")
            
        else:
            # СЛУЧАЙ 3: Проект есть и связь есть - просто обновляем
            existing_project.name = project_data['name']
            existing_project.url = project_data['url']
            existing_project.avatar_url = project_data['avatar_url']
            existing_project.category = project_data['category']
            existing_project.description = project_data['description']
            existing_project.is_active = project_data['is_active']
            updated_count += 1
            logger.debug(f"Updated existing project {project_key}")
    
    # ========== КОММИТИМ ПРОЕКТЫ ДО СТАТУСОВ ==========
    db.commit()
    logger.error(f"Projects saved: {created_count} created, {updated_count} updated, {linked_count} links added")
    
    # ========== 2. СИНХРОНИЗИРУЕМ СТАТУСЫ ==========
    if sync_statuses:
        # Получаем список ключей проектов (ТОЛЬКО тех, к которым есть доступ у пользователя)
        user_project_keys = db.query(Project.key).join(
            UserProject, UserProject.project_id == Project.id
        ).filter(
            UserProject.user_id == user_id
        ).all()
        
        project_keys_to_sync = [
            p["key"]
            for p in jira_projects
        ]
        
        if project_keys_to_sync:
            # Удаляем старые статусы для этих проектов
            deleted_count = db.query(ProjectStatusMapping).filter(
                ProjectStatusMapping.project_key.in_(project_keys_to_sync)
            ).delete(synchronize_session=False)
            logger.error(f"Deleted {deleted_count} old status mappings")
            
            # Синхронизируем статусы для каждого проекта
            for project_key in project_keys_to_sync:
                try:
                    statuses_url = f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3/project/{project_key}/statuses"
                    logger.error(
                        f"Project statuses request: "
                        f"project={project_key}, "
                        f"instance={instance_name}, "
                        f"cloud_id={cloud_id}"
                    )
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
                                logger.error(f"Status '{status_name}' (category='{category_key}') classified by name heuristic")
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
                        logger.error(f"Synced {len(unique_statuses)} statuses for {project_key}")
                    else:
                        logger.error(
                            f"Failed to get statuses for {project_key}: "
                            f"{statuses_response.status_code} {statuses_response.text}"
                        )
                except Exception as e:
                    logger.error(f"Failed to sync statuses for {project_key}: {e}")
                    db.rollback()
                    # Продолжаем со следующим проектом
            
            db.commit()
    
    logger.error(f"Sync completed: projects created={created_count}, updated={updated_count}, "
                f"links added={linked_count}, statuses synced={statuses_synced}")
    
    return {
        'created': created_count,
        'updated': updated_count,
        'linked': linked_count,  # Добавили в ответ
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
            statuses_response = _make_jira_request_with_refresh(statuses_url, token, db, user_id)
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
                logger.error(f"Refreshed statuses for {project.key}")
            else:
                logger.error(
                    f"Failed to get statuses for {project.key}: "
                    f"{statuses_response.status_code} {statuses_response.text}"
                )
        except Exception as e:
            logger.error(f"Failed to refresh statuses for {project.key}: {e}")
            db.rollback()
    
    return {
        'projects_processed': len(projects),
        'statuses_updated': statuses_updated
    }