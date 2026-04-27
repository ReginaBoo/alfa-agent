"""
Расчёт Activity Score — активности сотрудника
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models import JiraIssue
from app.core.statuses import CLOSED_STATUS
from app.services.project_service import get_project_id_by_key
from app.db.timescale import timescale_engine
from app.db.models.metrics import UserMetric
from sqlalchemy.orm import Session as TimescaleSession

logger = logging.getLogger(__name__)


def calculate_activity_score(
    db: Session,
    assignee_account_id: str,
    project_key: str,
    period_days: int = 30
) -> float:
    """
    Рассчитывает Activity Score сотрудника (0-100)
    
    Компоненты:
    - Количество закрытых задач (50 баллов максимум)
    - Количество обновлений задач (30 баллов максимум)
    - Количество созданных задач (20 баллов максимум)
    """
    
    cutoff_date = datetime.utcnow() - timedelta(days=period_days)
    
    # 1. Закрытые задачи (50 баллов)
    closed_tasks = db.query(JiraIssue).filter(
        JiraIssue.assignee_account_id == assignee_account_id,
        JiraIssue.project_key == project_key,
        JiraIssue.status.in_(CLOSED_STATUS),
        JiraIssue.updated_at >= cutoff_date
    ).count()
    
    tasks_score = min(closed_tasks * 2.5, 50)  # 20 задач = 50 баллов
    
    # 2. Обновления задач (30 баллов)
    updates = db.query(JiraIssue).filter(
        JiraIssue.assignee_account_id == assignee_account_id,
        JiraIssue.project_key == project_key,
        JiraIssue.updated_at >= cutoff_date
    ).count()
    
    updates_score = min(updates * 1, 30)  # 30 обновлений = 30 баллов
    
    # 3. Созданные задачи (20 баллов)
    created_tasks = db.query(JiraIssue).filter(
        JiraIssue.reporter_account_id == assignee_account_id,
        JiraIssue.project_key == project_key,
        JiraIssue.created_at >= cutoff_date
    ).count()
    
    created_score = min(created_tasks * 2, 20)  # 10 задач = 20 баллов
    
    activity_score = tasks_score + updates_score + created_score
    activity_score = min(round(activity_score, 2), 100)
    
    return activity_score


def save_activity_score(
    db: Session,
    assignee_account_id: str,
    project_key: str,
    activity_score: float,
    period_days: int = 30
) -> None:
    """Сохраняет Activity Score в user_metrics (TimescaleDB)"""
    
    from app.db.session import SessionLocal
    from app.db.models import IntegrationToken
    
    period_end = datetime.utcnow()
    period_start = period_end - timedelta(days=period_days)
    
    # Находим user_id
    pg_db = SessionLocal()
    token = pg_db.query(IntegrationToken).filter(
        IntegrationToken.provider_user_id == assignee_account_id,
        IntegrationToken.provider == 'jira'
    ).first()
    pg_db.close()
    
    if not token:
        logger.warning(f"User not found for {assignee_account_id}")
        return
    
    user_id = token.user_id
    project_id = get_project_id_by_key(db, project_key)
    
    with TimescaleSession(timescale_engine) as ts_db:
        existing = ts_db.query(UserMetric).filter(
            UserMetric.user_id == user_id,
            UserMetric.project_id == project_id,
            UserMetric.period_start == period_start,
            UserMetric.period_end == period_end
        ).first()
        
        if existing:
            existing.activity_score = activity_score
            existing.calculated_at = datetime.utcnow()
        else:
            new_metric = UserMetric(
                user_id=user_id,
                project_id=project_id,
                period_start=period_start,
                period_end=period_end,
                activity_score=activity_score,
                calculated_at=datetime.utcnow()
            )
            ts_db.add(new_metric)
        
        ts_db.commit()
        logger.info(f"Saved Activity Score {activity_score} for user {user_id}, project {project_id}")