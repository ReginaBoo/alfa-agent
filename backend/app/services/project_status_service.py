# app/services/project_status_service.py

from typing import List
from sqlalchemy.orm import Session

from app.db.models.normalized import ProjectStatusMapping


class ProjectStatusService:

    @staticmethod
    def get_closed_statuses(
        db: Session,
        project_key: str
    ) -> List[str]:

        mappings = db.query(ProjectStatusMapping).filter(
            ProjectStatusMapping.project_key == project_key,
            ProjectStatusMapping.is_closed == True
        ).all()

        return [m.status_name.strip().lower() for m in mappings]

    @staticmethod
    def get_open_statuses(
        db: Session,
        project_key: str
    ) -> List[str]:

        mappings = db.query(ProjectStatusMapping).filter(
            ProjectStatusMapping.project_key == project_key,
            ProjectStatusMapping.is_open == True
        ).all()

        return [m.status_name for m in mappings]

    @staticmethod
    def get_in_progress_statuses(
        db: Session,
        project_key: str
    ) -> List[str]:

        mappings = db.query(ProjectStatusMapping).filter(
            ProjectStatusMapping.project_key == project_key,
            ProjectStatusMapping.is_in_progress == True
        ).all()

        return [m.status_name for m in mappings]