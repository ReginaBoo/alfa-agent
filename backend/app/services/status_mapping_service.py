# app/services/status_mapping_service.py

import logging
from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.db.models.normalized import ProjectStatusMapping
from app.jira.client import JiraClient

logger = logging.getLogger(__name__)


class StatusMappingService:
    """Сервис для управления маппингом статусов Jira проектов"""
    
    @staticmethod
    async def sync_project_statuses(
        db: Session,
        project_key: str,
        jira_client: JiraClient,
        synced_by_account_id: str = None
    ) -> List[ProjectStatusMapping]:
        """
        Синхронизирует статусы проекта из Jira API
        
        Args:
            db: Сессия БД
            project_key: Ключ проекта (SCRUM, TEST, и т.д.)
            jira_client: Клиент Jira с авторизацией
            synced_by_account_id: ID пользователя, который запустил синхронизацию
        
        Returns:
            List[ProjectStatusMapping]: Сохранённые маппинги
        """
        try:
            # Получаем статусы из Jira API
            url = f"/rest/api/3/project/{project_key}/statuses"
            statuses_data = await jira_client.get(url)
            
            if not statuses_data:
                logger.warning(f"No statuses data for project {project_key}")
                return []
            
            saved_mappings = []
            
            for issue_type_data in statuses_data:
                for status in issue_type_data.get("statuses", []):
                    status_name = status.get("name")
                    status_category = status.get("statusCategory", {})
                    category_key = status_category.get("key")  # "todo", "in-progress", "done"
                    category_name = status_category.get("name")
                    
                    # Определяем роли на основе категории Jira
                    is_open = category_key in ["todo", "in-progress"]
                    is_in_progress = category_key == "in-progress"
                    is_closed = category_key == "done"
                    
                    # Ищем существующий маппинг
                    existing = db.query(ProjectStatusMapping).filter(
                        and_(
                            ProjectStatusMapping.project_key == project_key,
                            ProjectStatusMapping.status_name == status_name
                        )
                    ).first()
                    
                    if existing:
                        # Обновляем существующий
                        existing.is_open = is_open
                        existing.is_in_progress = is_in_progress
                        existing.is_closed = is_closed
                        existing.jira_category = category_key
                        existing.last_synced_at = datetime.utcnow()
                        existing.synced_by_account_id = synced_by_account_id
                        saved_mappings.append(existing)
                    else:
                        # Создаём новый
                        new_mapping = ProjectStatusMapping(
                            project_key=project_key,
                            status_name=status_name,
                            is_open=is_open,
                            is_in_progress=is_in_progress,
                            is_closed=is_closed,
                            jira_category=category_key,
                            last_synced_at=datetime.utcnow(),
                            synced_by_account_id=synced_by_account_id
                        )
                        db.add(new_mapping)
                        saved_mappings.append(new_mapping)
            
            db.commit()
            logger.info(f"Synced {len(saved_mappings)} statuses for project {project_key}")
            return saved_mappings
            
        except Exception as e:
            logger.error(f"Failed to sync statuses for {project_key}: {e}")
            db.rollback()
            raise
    
    @staticmethod
    def get_status_role(
        db: Session,
        project_key: str,
        status_name: str
    ) -> Dict[str, bool]:
        """
        Получает роль статуса для конкретного проекта
        
        Returns:
            Dict: {is_open, is_in_progress, is_closed}
        """
        mapping = db.query(ProjectStatusMapping).filter(
            and_(
                ProjectStatusMapping.project_key == project_key,
                ProjectStatusMapping.status_name == status_name
            )
        ).first()
        
        if mapping:
            return {
                "is_open": mapping.is_open,
                "is_in_progress": mapping.is_in_progress,
                "is_closed": mapping.is_closed
            }
        
        # Fallback: эвристика по названию
        return StatusMappingService._heuristic_status_role(status_name)
    
    @staticmethod
    def get_open_statuses_for_project(
        db: Session,
        project_key: str
    ) -> List[str]:
        """Возвращает список статусов, которые считаются открытыми для проекта"""
        mappings = db.query(ProjectStatusMapping).filter(
            and_(
                ProjectStatusMapping.project_key == project_key,
                ProjectStatusMapping.is_open == True
            )
        ).all()
        
        return [m.status_name for m in mappings]
    
    @staticmethod
    def get_closed_statuses_for_project(
        db: Session,
        project_key: str
    ) -> List[str]:
        """Возвращает список статусов, которые считаются закрытыми для проекта"""
        mappings = db.query(ProjectStatusMapping).filter(
            and_(
                ProjectStatusMapping.project_key == project_key,
                ProjectStatusMapping.is_closed == True
            )
        ).all()
        
        return [m.status_name for m in mappings]
    
    @staticmethod
    def get_in_progress_statuses_for_project(
        db: Session,
        project_key: str
    ) -> List[str]:
        """Возвращает список статусов, которые считаются 'в работе' для проекта"""
        mappings = db.query(ProjectStatusMapping).filter(
            and_(
                ProjectStatusMapping.project_key == project_key,
                ProjectStatusMapping.is_in_progress == True
            )
        ).all()
        
        return [m.status_name for m in mappings]
    
    @staticmethod
    def _heuristic_status_role(status_name: str) -> Dict[str, bool]:
        """Эвристика для определения роли статуса по названию"""
        status_lower = status_name.lower()
        
        # Закрытые статусы
        closed_keywords = [
            'done', 'closed', 'resolved', 'completed', 'finished',
            'готово', 'выполнено', 'закрыт', 'завершен'
        ]
        if any(kw in status_lower for kw in closed_keywords):
            return {"is_open": False, "is_in_progress": False, "is_closed": True}
        
        # Статусы в работе
        in_progress_keywords = [
            'progress', 'review', 'testing', 'development', 'deploy',
            'работе', 'тестирование', 'разработка', 'проверк', 'ревью'
        ]
        if any(kw in status_lower for kw in in_progress_keywords):
            return {"is_open": True, "is_in_progress": True, "is_closed": False}
        
        # Открытые статусы (по умолчанию)
        return {"is_open": True, "is_in_progress": False, "is_closed": False}