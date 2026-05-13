"""
Расчёт Workload Index (WI) — индекса загрузки сотрудников.
Формула: WI = (вес открытых задач) / (средняя скорость закрытия SP за N недель)
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta

from app.db.models import JiraIssue
from app.core.statuses import OPEN_STATUSES, CLOSED_STATUS, IN_PROGRESS_STATUSES, get_issue_weight
from app.db.timescale import get_timescale_db
from app.services.project_service import get_project_id_by_key
from app.services.metrics.activity_score import calculate_activity_score, save_activity_score

logger = logging.getLogger(__name__)


def calculate_workload_index(
    db: Session,
    assignee_account_id: str,
    project_key: str,
    weeks: int = 2
) -> Optional[float]:
    """
    Рассчитывает Workload Index для конкретного сотрудника.
    
    Формула: 
        WI = (вес открытых задач) / (средняя скорость закрытия SP за N недель)
    
    Args:
        db: Сессия PostgreSQL
        assignee_account_id: ID исполнителя в Jira
        project_key: Ключ проекта
        weeks: Количество недель для расчёта скорости (по умолчанию 2)
        
    Returns:
        float: Индекс загрузки или None если данных недостаточно
    """
    
    # 1. Суммируем вес открытых задач
    open_issues = db.query(JiraIssue).filter(
        JiraIssue.assignee_account_id == assignee_account_id,
        JiraIssue.project_key == project_key,
        JiraIssue.status.in_(OPEN_STATUSES)
    ).all()
    
    open_weight = 0
    for issue in open_issues:
        weight = get_issue_weight(issue.issue_type, issue.story_points)
        open_weight += weight
    
    logger.info(f"Open weight for {assignee_account_id}: {open_weight}")
    
    # 2. Считаем среднюю скорость закрытия за N недель
    cutoff_date = datetime.utcnow() - timedelta(weeks=weeks)
    
    closed_issues = db.query(JiraIssue).filter(
        JiraIssue.assignee_account_id == assignee_account_id,
        JiraIssue.project_key == project_key,
        JiraIssue.status.in_(CLOSED_STATUS),
        JiraIssue.updated_at >= cutoff_date
    ).all()
    
    total_weight_closed = 0
    for issue in closed_issues:
        weight = get_issue_weight(issue.issue_type, issue.story_points)
        total_weight_closed += weight
    
    weeks_count = weeks
    
    if weeks_count > 0 and total_weight_closed > 0:
        avg_velocity = total_weight_closed / weeks_count
    else:
        # Если нет истории, используем минимальную скорость 1 SP в неделю
        avg_velocity = 1.0
    
    logger.info(f"Avg velocity for {assignee_account_id}: {avg_velocity} SP/week")
    
    # 3. WI = открытый вес / средняя скорость
    if avg_velocity > 0:
        wi = open_weight / avg_velocity
    else:
        wi = open_weight
    
    # 4. Штраф за многозадачность (>3 задач в статусе In Progress)
    tasks_in_progress = db.query(JiraIssue).filter(
        JiraIssue.assignee_account_id == assignee_account_id,
        JiraIssue.project_key == project_key,
        JiraIssue.status.in_(IN_PROGRESS_STATUSES)
    ).count()
    
    if tasks_in_progress > 3:
        extra_tasks = tasks_in_progress - 3
        penalty = 1 + (extra_tasks * 0.2)  # +20% за каждую лишнюю задачу
        wi = wi * penalty
        logger.info(f"Penalty applied: {penalty} (tasks in progress: {tasks_in_progress})")
    
    return round(wi, 2)


def get_workload_status(wi: float) -> dict:
    """
    Возвращает статус загрузки на основе WI.
    
    Returns:
        dict: {status, status_text, color}
    """
    if wi < 0.7:
        return {'status': 'underloaded', 'status_text': 'Недогруз', 'color': 'blue'}
    elif wi <= 1.1:
        return {'status': 'normal', 'status_text': 'Оптимально', 'color': 'green'}
    else:
        return {'status': 'overloaded', 'status_text': 'Перегруз', 'color': 'red'}


def calculate_team_workload(
    db: Session,
    project_key: str,
    weeks: int = 2
) -> List[Dict[str, Any]]:
    """
    Рассчитывает Workload Index для всех сотрудников проекта.
    
    Returns:
        List[Dict]: Список с результатами для каждого сотрудника
    """
    
    assignees = db.query(JiraIssue.assignee_account_id).filter(
        JiraIssue.project_key == project_key,
        JiraIssue.assignee_account_id.isnot(None)
    ).distinct().all()
    
    results = []
    for (assignee_id,) in assignees:
        wi = calculate_workload_index(db, assignee_id, project_key, weeks)
        if wi is not None:
            status_info = get_workload_status(wi)
            results.append({
                'assignee_account_id': assignee_id,
                'workload_index': wi,
                'status': status_info['status'],
                'status_text': status_info['status_text'],
                'color': status_info['color']
            })
    
    results.sort(key=lambda x: x['workload_index'], reverse=True)
    return results


def save_workload_metric(
    db: Session,  # ← добавить параметр
    assignee_account_id: str,
    project_key: str,
    wi: float,
    period_weeks: int = 2
) -> None:
    from app.db.models.metrics import MetricRaw
    from app.services.project_service import get_project_id_by_key
    
    timescale_db = next(get_timescale_db())
    
    # Получаем реальный project_id
    project_id = get_project_id_by_key(db, project_key)
    
    # Получаем user_id
    from app.db.models import IntegrationToken
    token = db.query(IntegrationToken).filter(
        IntegrationToken.provider_user_id == assignee_account_id,
        IntegrationToken.provider == 'jira'
    ).first()
    user_id = token.user_id if token else 0
    
    raw_metric = MetricRaw(
        time=datetime.utcnow(),
        project_id=project_id,  # реальный ID
        user_id=user_id,        # реальный ID
        metric_name='workload_index',
        value=wi,
        dimensions={
            'assignee_account_id': assignee_account_id,
            'project_key': project_key,
            'period_weeks': period_weeks
        }
    )
    timescale_db.add(raw_metric)
    timescale_db.commit()
    
    logger.info(f"Saved workload index {wi} for {assignee_account_id} in {project_key}")




def save_workload_to_user_metrics(
    assignee_account_id: str,
    project_key: str,
    wi: float,
    period_start: datetime,
    period_end: datetime
) -> None:
    """Сохраняет WI в таблицу user_metrics (TimescaleDB)"""
    
    from app.db.timescale import timescale_engine
    from app.db.models import IntegrationToken
    from app.db.models.metrics import UserMetric
    from sqlalchemy.orm import Session
    
    # Находим user_id через integration_tokens (в PostgreSQL)
    from app.db.session import SessionLocal
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
    
    # ПОЛУЧАЕМ РЕАЛЬНЫЙ project_id
    project_id = get_project_id_by_key(pg_db, project_key)
    
    # Сохраняем в TimescaleDB
    with Session(timescale_engine) as ts_db:
        existing = ts_db.query(UserMetric).filter(
            UserMetric.user_id == user_id,
            UserMetric.project_id == project_id,
            UserMetric.period_start == period_start,
            UserMetric.period_end == period_end
        ).first()
        
        if existing:
            existing.workload_index = wi
            existing.calculated_at = datetime.utcnow()
        else:
            new_metric = UserMetric(
                user_id=user_id,
                project_id=project_id,
                period_start=period_start,
                period_end=period_end,
                workload_index=wi,
                calculated_at=datetime.utcnow()
            )
            ts_db.add(new_metric)
        
        ts_db.commit()
        logger.info(f"Saved WI {wi} to user_metrics for user {user_id}, project {project_id}")


def save_workload_to_metrics_raw(
    assignee_account_id: str,
    project_key: str,
    wi: float,
    period_weeks: int = 2
) -> None:
    """Сохраняет WI в TimescaleDB (metrics_raw)"""
    
    from app.db.models.metrics import MetricRaw
    from app.db.timescale import timescale_engine
    from sqlalchemy.orm import Session
    
    #  ПОЛУЧАЕМ РЕАЛЬНЫЙ project_id
    from app.db.session import SessionLocal
    pg_db = SessionLocal()
    project_id = get_project_id_by_key(pg_db, project_key)
    pg_db.close()
    
    with Session(timescale_engine) as ts_db:
        raw_metric = MetricRaw(
            time=datetime.utcnow(),
            project_id=project_id,
            user_id=0,  # user_id будет позже
            metric_name='workload_index',
            value=wi,
            dimensions={
                'assignee_account_id': assignee_account_id,
                'project_key': project_key,
                'period_weeks': period_weeks
            }
        )
        ts_db.add(raw_metric)
        ts_db.commit()
    
    logger.info(f"Saved WI {wi} to metrics_raw for {assignee_account_id}, project {project_id}")


# В функции calculate_and_save_workload_index добавьте после сохранения WI:
def calculate_and_save_workload_index(
    db: Session,
    assignee_account_id: str,
    project_key: str,
    weeks: int = 2
) -> Optional[float]:
    """Рассчитывает и сохраняет WI и Activity Score"""
    
    wi = calculate_workload_index(db, assignee_account_id, project_key, weeks)
    
    if wi is not None:
        period_end = datetime.utcnow()
        period_start = period_end - timedelta(weeks=weeks)
        period_days = weeks * 7
        
        # Сохраняем WI
        save_workload_to_user_metrics(
            assignee_account_id, project_key, wi, period_start, period_end
        )
        save_workload_to_metrics_raw(assignee_account_id, project_key, wi, weeks)
        
        # Сохраняем Activity Score
        activity_score = calculate_activity_score(db, assignee_account_id, project_key, period_days)
        save_activity_score(db, assignee_account_id, project_key, activity_score, period_days)
    
    return wi