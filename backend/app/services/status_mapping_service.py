# app/services/status_mapping_service.py

import logging
from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
from sqlalchemy.dialects.postgresql import insert

from app.db.models.normalized import ProjectStatusMapping
from app.jira.client import JiraClient

logger = logging.getLogger(__name__)


class StatusMappingService:
    """Сервис для управления маппингом статусов Jira проектов"""
    
    @staticmethod
    async def sync_project_statuses(
        db: Session,
        project_key: str,
        cloud_id: str,  # ← добавить cloud_id
        jira_client: JiraClient,
        synced_by_account_id: str = None
    ) -> List[ProjectStatusMapping]:
        """
        Синхронизирует статусы проекта из Jira API.
        Использует дедупликацию и upsert для избежания конфликтов.
        """
        try:
            # 1. Получаем данные из Jira API через _request
            url = f"/rest/api/3/project/{project_key}/statuses"
            statuses_data = await jira_client._request(
                cloud_id=cloud_id,
                endpoint=url,
                method="GET",
                user_id=None  # или нужный user_id
            )
            
            if not statuses_data:
                logger.warning(f"No statuses data for project {project_key}")
                return []
            
            # 2. ДЕДУПЛИКАЦИЯ: Собираем уникальные статусы
            unique_statuses = {}
            for issue_type_data in statuses_data:
                for status in issue_type_data.get("statuses", []):
                    status_name = status.get("name")
                    if status_name not in unique_statuses:
                        unique_statuses[status_name] = status

            logger.info(f"Found {len(unique_statuses)} unique statuses for project {project_key}")

            # 3. Подготавливаем данные для массовой вставки/обновления
            mappings_to_upsert = []
            for status_name, status in unique_statuses.items():
                status_category = status.get("statusCategory", {})
                category_key = status_category.get("key")  # "todo", "in-progress", "done"
                
                # Определяем роли на основе категории Jira
                is_open = category_key in ["todo", "in-progress"]
                is_in_progress = category_key == "in-progress"
                is_closed = category_key == "done"
                
                mappings_to_upsert.append({
                    "project_key": project_key,
                    "status_name": status_name,
                    "is_open": is_open,
                    "is_in_progress": is_in_progress,
                    "is_closed": is_closed,
                    "jira_category": category_key,
                    "last_synced_at": datetime.utcnow(),
                    "synced_by_account_id": synced_by_account_id,
                })

            # 4. UPSERT: Вставка или обновление (решает проблему дубликатов)
            if mappings_to_upsert:
                stmt = insert(ProjectStatusMapping).values(mappings_to_upsert)
                
                # Что делать при конфликте (уникальность project_key, status_name)
                update_dict = {
                    "is_open": stmt.excluded.is_open,
                    "is_in_progress": stmt.excluded.is_in_progress,
                    "is_closed": stmt.excluded.is_closed,
                    "jira_category": stmt.excluded.jira_category,
                    "last_synced_at": stmt.excluded.last_synced_at,
                    "synced_by_account_id": stmt.excluded.synced_by_account_id,
                }
                stmt = stmt.on_conflict_do_update(
                    constraint="uq_project_status",
                    set_=update_dict
                )
                
                db.execute(stmt)
                db.commit()
                logger.info(f"Upserted {len(mappings_to_upsert)} statuses for project {project_key}")

                # Возвращаем обновленные/созданные объекты
                saved_mappings = db.query(ProjectStatusMapping).filter(
                    ProjectStatusMapping.project_key == project_key,
                    ProjectStatusMapping.status_name.in_([m["status_name"] for m in mappings_to_upsert])
                ).all()
                return saved_mappings
            
            return []
            
        except Exception as e:
            logger.error(f"Failed to sync statuses for {project_key}: {e}")
            db.rollback()
            raise

    # Остальные методы (get_status_role, get_open_statuses_for_project и т.д.) остаются без изменений
    @staticmethod
    def get_status_role(
        db: Session,
        project_key: str,
        status_name: str
    ) -> Dict[str, bool]:
        """Получает роль статуса для конкретного проекта"""
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
        
        closed_keywords = [
            'done', 'closed', 'resolved', 'completed', 'finished',
            'готово', 'выполнено', 'закрыт', 'завершен'
        ]
        if any(kw in status_lower for kw in closed_keywords):
            return {"is_open": False, "is_in_progress": False, "is_closed": True}
        
        in_progress_keywords = [
            'progress', 'review', 'testing', 'development', 'deploy',
            'работе', 'тестирование', 'разработка', 'проверк', 'ревью'
        ]
        if any(kw in status_lower for kw in in_progress_keywords):
            return {"is_open": True, "is_in_progress": True, "is_closed": False}
        
        return {"is_open": True, "is_in_progress": False, "is_closed": False}