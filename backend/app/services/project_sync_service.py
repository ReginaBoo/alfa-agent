"""
Сервис для синхронизации проектов из Jira в БД
"""

import logging
from sqlalchemy.orm import Session
from app.db.models.core import Project, UserProject
from app.db.models import IntegrationToken
import requests

logger = logging.getLogger(__name__)


def sync_projects_from_jira(
    db: Session,
    user_id: int,
    instance_name: str,
    token_instance_id: str = None,
    token_access_token: str = None
) -> dict:
    """
    Синхронизирует проекты из Jira в таблицу core.projects
    
    Args:
        db: Сессия БД
        user_id: ID пользователя в нашей системе
        instance_name: Имя сайта Jira
        token_instance_id: cloud_id (опционально)
        token_access_token: access_token (опционально)
    
    Returns:
        dict: {created, updated, total}
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
        access_token = token.access_token
    else:
        cloud_id = token_instance_id
        access_token = token_access_token
    
    # Запрашиваем проекты из Jira API
    url = f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3/project"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    
    jira_projects = response.json()
    
    created_count = 0
    updated_count = 0
    
    for jp in jira_projects:
        existing = db.query(Project).filter(Project.key == jp['key']).first()
        
        project_data = {
            'key': jp['key'],
            'name': jp['name'],
            'jira_project_key': jp['key'],
            'url': jp.get('self'),
            'avatar_url': jp.get('avatarUrls', {}).get('48x48'),
            'category': jp.get('projectTypeKey')
        }
        
        if existing:
            # Обновляем существующий проект
            existing.name = project_data['name']
            existing.url = project_data['url']
            existing.avatar_url = project_data['avatar_url']
            existing.category = project_data['category']
            updated_count += 1
        else:
            # Создаём новый проект
            project = Project(**project_data)
            db.add(project)
            db.flush()
            
            # Связываем с пользователем
            user_project = UserProject(
                user_id=user_id,
                project_id=project.id,
                role='owner'
            )
            db.add(user_project)
            created_count += 1
    
    db.commit()
    
    logger.info(f"Synced projects: created={created_count}, updated={updated_count}")
    
    return {
        'created': created_count,
        'updated': updated_count,
        'total': created_count + updated_count
    }