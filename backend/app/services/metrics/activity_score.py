"""
Расчёт Activity Score — активности сотрудника
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models import JiraIssue
from app.db.models.normalized import IssueChangelog, ProjectStatusMapping
from app.services.project_service import get_project_id_by_key
from app.db.timescale import timescale_engine
from app.db.models.metrics import UserMetric
from sqlalchemy.orm import Session as TimescaleSession
from app.services.project_status_service import ProjectStatusService

logger = logging.getLogger(__name__)


def _get_date_of_closing(db: Session, issue_key: str, closed_statuses: list) -> Optional[datetime]:
    """
    Определяет дату, когда задача была закрыта (перешла в закрытый статус).
    Использует changelog для точного определения момента закрытия.
    """
    # Ищем первый переход в закрытый статус
    closing_event = db.query(IssueChangelog).filter(
        IssueChangelog.issue_key == issue_key,
        IssueChangelog.field_name == 'status',
        IssueChangelog.to_value.in_(closed_statuses)
    ).order_by(IssueChangelog.changed_at.asc()).first()
    
    if closing_event:
        return closing_event.changed_at
    
    # Fallback: используем updated_at
    issue = db.query(JiraIssue).filter(JiraIssue.issue_key == issue_key).first()
    return issue.updated_at if issue else None


def _get_closed_tasks_for_user(
    db: Session,
    assignee_account_id: str,
    project_key: str,
    closed_statuses: list,
    cutoff_date: datetime
) -> int:
    """
    Подсчитывает количество задач, закрытых пользователем за период.
    Учитывает, что пользователь мог быть назначен на задачу в момент закрытия.
    """
    # Получаем все закрытые задачи проекта
    closed_issues = db.query(JiraIssue).filter(
        JiraIssue.project_key == project_key,
        JiraIssue.status.in_(closed_statuses)
    ).all()
    
    count = 0
    for issue in closed_issues:
        # Проверяем, был ли пользователь assignee на момент закрытия
        closing_date = _get_date_of_closing(db, issue.issue_key, closed_statuses)
        
        if not closing_date or closing_date < cutoff_date:
            continue
        
        # Проверяем, был ли пользователь назначен на задачу в момент закрытия
        # Для этого смотрим changelog назначений
        last_assignee_before_close = db.query(IssueChangelog).filter(
            IssueChangelog.issue_key == issue.issue_key,
            IssueChangelog.field_name == 'assignee',
            IssueChangelog.changed_at <= closing_date
        ).order_by(IssueChangelog.changed_at.desc()).first()
        
        assignee_at_close = last_assignee_before_close.to_value if last_assignee_before_close else issue.assignee_account_id
        
        if assignee_at_close == assignee_account_id:
            count += 1
    
    return count


def _get_updates_from_changelog(
    db: Session,
    assignee_account_id: str,
    project_key: str,
    cutoff_date: datetime
) -> int:
    """
    Подсчитывает количество обновлений, сделанных пользователем.
    Включает: комментарии, переходы статусов, изменения полей.
    """
    updates = db.query(IssueChangelog).filter(
        IssueChangelog.author_account_id == assignee_account_id,
        IssueChangelog.changed_at >= cutoff_date
    ).join(
        JiraIssue, IssueChangelog.issue_key == JiraIssue.issue_key
    ).filter(
        JiraIssue.project_key == project_key
    ).count()
    
    return updates


def calculate_activity_score(
    db: Session,
    assignee_account_id: str,
    project_key: str,
    period_days: int = 30
) -> float:
    """
    Рассчитывает Activity Score сотрудника (0-100)
    
    Компоненты (согласно требованиям):
    - Количество закрытых задач (50 баллов максимум)
    - Количество обновлений задач (30 баллов максимум)
    - Количество созданных задач (20 баллов максимум)
    """
    
    cutoff_date = datetime.utcnow() - timedelta(days=period_days)
    
    # Получаем закрытые статусы для этого проекта
    closed_statuses = ProjectStatusService.get_closed_statuses(db, project_key)
    
    # 1. Закрытые задачи (50 баллов максимум)
    # Используем changelog для определения даты закрытия
    closed_tasks = _get_closed_tasks_for_user(
        db, assignee_account_id, project_key, closed_statuses, cutoff_date
    )
    tasks_score = min(closed_tasks * 2.5, 50)  # 20 задач = 50 баллов
    
    # 2. Обновления задач через changelog (30 баллов максимум)
    # Считаем ВСЕ обновления, сделанные пользователем
    updates_count = _get_updates_from_changelog(db, assignee_account_id, project_key, cutoff_date)
    updates_score = min(updates_count * 1.0, 30)  # 30 обновлений = 30 баллов
    
    # 3. Созданные задачи (20 баллов максимум)
    created_tasks = db.query(JiraIssue).filter(
        JiraIssue.reporter_account_id == assignee_account_id,
        JiraIssue.project_key == project_key,
        JiraIssue.created_at >= cutoff_date
    ).count()
    created_score = min(created_tasks * 2.0, 20)  # 10 задач = 20 баллов
    
    activity_score = tasks_score + updates_score + created_score
    activity_score = min(round(activity_score, 2), 100)
    
    logger.info(f"Activity Score for {assignee_account_id} in {project_key}: {activity_score} "
                f"(closed={closed_tasks}/{tasks_score}, "
                f"updates={updates_count}/{updates_score}, "
                f"created={created_tasks}/{created_score})")
    
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