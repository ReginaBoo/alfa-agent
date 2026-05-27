"""
Сервис для работы с проектами
"""

from sqlalchemy.orm import Session
from app.db.models.core import Project


def get_project_id_by_key(db: Session, project_key: str) -> int:
    """
    Возвращает project_id по ключу проекта
    """
    project = db.query(Project).filter(Project.key == project_key).first()
    return project.id if project else 0