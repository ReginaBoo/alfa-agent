# app/services/metrics/health_score.py
"""
Расчёт Project Health Score
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.db.models import JiraIssue
from app.db.timescale import timescale_engine
from app.db.models.metrics import ProjectHealth
from app.core.statuses import CLOSED_STATUS

logger = logging.getLogger(__name__)


def calculate_stability_score(
    db: Session,
    project_key: str,
    period_days: int = 30
) -> float:
    """
    Рассчитывает Stability Score — стабильность продукта.
    Формула: (1 - баги / всего задач) * 100
    
    Args:
        db: Сессия PostgreSQL
        project_key: Ключ проекта
        period_days: Период в днях
    
    Returns:
        float: Stability Score (0-100)
    """
    
    cutoff_date = datetime.utcnow() - timedelta(days=period_days)
    
    # Всего задач за период
    total_issues = db.query(JiraIssue).filter(
        JiraIssue.project_key == project_key,
        JiraIssue.created_at >= cutoff_date
    ).count()
    
    if total_issues == 0:
        return 100.0
    
    # Баги за период
    bugs = db.query(JiraIssue).filter(
        JiraIssue.project_key == project_key,
        JiraIssue.issue_type.in_(['Bug', 'Баг', 'Ошибка']),
        JiraIssue.created_at >= cutoff_date
    ).count()
    
    # Чем меньше багов, тем выше стабильность
    stability_score = (1 - bugs / total_issues) * 100
    return round(stability_score, 2)


def calculate_workload_balance(
    db: Session,
    project_key: str,
    period_days: int = 30
) -> float:
    """
    Рассчитывает Workload Balance — равномерность загрузки команды.
    На основе количества задач на исполнителя.
    
    Args:
        db: Сессия PostgreSQL
        project_key: Ключ проекта
        period_days: Период в днях
    
    Returns:
        float: Workload Balance (0-100)
    """
    
    cutoff_date = datetime.utcnow() - timedelta(days=period_days)
    
    # Количество задач на исполнителя
    from sqlalchemy import func
    tasks_per_user = db.query(
        JiraIssue.assignee_account_id,
        func.count(JiraIssue.id).label('task_count')
    ).filter(
        JiraIssue.project_key == project_key,
        JiraIssue.assignee_account_id.isnot(None),
        JiraIssue.created_at >= cutoff_date
    ).group_by(JiraIssue.assignee_account_id).all()
    
    if not tasks_per_user:
        return 100.0
    
    counts = [t[1] for t in tasks_per_user]
    max_tasks = max(counts)
    min_tasks = min(counts)
    
    if max_tasks == min_tasks:
        return 100.0
    
    # Коэффициент равномерности
    balance = (1 - (max_tasks - min_tasks) / max_tasks) * 100
    return round(balance, 2)


def calculate_health_score(
    db: Session,
    project_key: str,
    period_days: int = 30
) -> Dict[str, Any]:
    """
    Рассчитывает общий Health Score проекта.
    
    Формула:
        Health = (SLA × 0.3) + (Stability × 0.3) + (WorkloadBalance × 0.3) + (DeadlineStability × 0.1)
    
    Returns:
        Dict: {health_score, status, components}
    """
    
    from app.services.metrics.sla_score import calculate_sla_score, calculate_deadline_stability
    
    # Получаем компоненты
    sla = calculate_sla_score(db, project_key=project_key, period_days=period_days)
    stability = calculate_stability_score(db, project_key=project_key, period_days=period_days)
    deadline_stability = calculate_deadline_stability(db, project_key=project_key, period_days=period_days)
    workload_balance = calculate_workload_balance(db, project_key=project_key, period_days=period_days)
    
    # Веса
    weights = {
        'sla': 0.3,
        'stability': 0.3,
        'workload_balance': 0.3,
        'deadline_stability': 0.1
    }
    
    # Расчёт Health Score
    health_score = (
        sla['sla_score'] * weights['sla'] +
        stability * weights['stability'] +
        workload_balance * weights['workload_balance'] +
        deadline_stability['stability_score'] * weights['deadline_stability']
    )
    health_score = round(health_score, 2)
    
    # Определяем статус
    if health_score >= 80:
        status = 'green'
        status_text = 'Здоров'
    elif health_score >= 50:
        status = 'yellow'
        status_text = 'Риск'
    else:
        status = 'red'
        status_text = 'Критично'
    
    return {
        'health_score': health_score,
        'status': status,
        'status_text': status_text,
        'components': {
            'sla_score': sla['sla_score'],
            'stability_score': stability,
            'workload_balance': workload_balance,
            'deadline_stability': deadline_stability['stability_score']
        }
    }


def save_health_score(
    db: Session,
    project_key: str,
    health_data: Dict[str, Any],
    period_days: int = 30
) -> None:
    """
    Сохраняет Health Score в project_health (TimescaleDB)
    """
    from sqlalchemy.orm import Session as TimescaleSession
    
    period_end = datetime.utcnow()
    period_start = period_end - timedelta(days=period_days)
    
    # TODO: найти project_id по project_key
    project_id = 0
    
    with TimescaleSession(timescale_engine) as ts_db:
        new_health = ProjectHealth(
            project_id=project_id,
            period_start=period_start,
            period_end=period_end,
            health_score=health_data['health_score'],
            status=health_data['status'],
            calculated_at=datetime.utcnow()
        )
        ts_db.add(new_health)
        ts_db.commit()
        
        logger.info(f"Saved Health Score {health_data['health_score']} for project {project_key} ({health_data['status_text']})")