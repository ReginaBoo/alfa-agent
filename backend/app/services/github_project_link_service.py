# app/services/github_project_link_service.py

import logging
from sqlalchemy.orm import Session
from app.db.models.core import Project
from app.db.models.normalized import GithubIssue

logger = logging.getLogger(__name__)


def link_repo_to_project(
    db: Session,
    repo_full_name: str,
    project_key: str,
    user_id: int
) -> dict:
    """
    Связывает GitHub репозиторий с проектом в системе.
    
    Args:
        db: Сессия БД
        repo_full_name: Полное имя репозитория (owner/repo)
        project_key: Ключ проекта в core.projects
        user_id: ID пользователя
    
    Returns:
        dict: Результат операции
    """
    # Находим проект
    project = db.query(Project).filter(
        Project.key == project_key,
        Project.owner_id == user_id
    ).first()
    
    if not project:
        raise ValueError(f"Project {project_key} not found or no access")
    
    # Сохраняем связь в проекте
    project.github_repo = repo_full_name
    
    # Обновляем все существующие issues этого репозитория
    updated_count = db.query(GithubIssue).filter(
        GithubIssue.repo_full_name == repo_full_name,
        GithubIssue.project_id.is_(None)
    ).update({"project_id": project.id})
    
    db.commit()
    
    logger.info(f"Linked repo {repo_full_name} to project {project_key}, updated {updated_count} issues")
    
    return {
        "success": True,
        "project_key": project_key,
        "repo_full_name": repo_full_name,
        "updated_issues": updated_count
    }


def get_project_by_repo(db: Session, repo_full_name: str) -> Project:
    """
    Получает проект по GitHub репозиторию.
    """
    return db.query(Project).filter(
        Project.github_repo == repo_full_name
    ).first()