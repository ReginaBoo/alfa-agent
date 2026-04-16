# app/services/metrics/sla_score.py
"""
Расчёт SLA Score и Deadline Stability
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models import JiraIssue
from app.core.statuses import CLOSED_STATUS

logger = logging.getLogger(__name__)


def calculate_sla_score(
    db: Session,
    project_key: str,
    assignee_account_id: Optional[str] = None,
    period_days: int = 30
) -> Dict[str, Any]:
    """
    Рассчитывает SLA Score — процент задач, закрытых в срок.
    
    Args:
        db: Сессия PostgreSQL
        project_key: Ключ проекта
        assignee_account_id: ID исполнителя (если None — по всем)
        period_days: Период в днях (по умолчанию 30)
    
    Returns:
        Dict: {sla_score, total_closed, on_time, late}
    """
    
    cutoff_date = datetime.utcnow() - timedelta(days=period_days)
    
    # Базовый запрос
    query = db.query(JiraIssue).filter(
        JiraIssue.project_key == project_key,
        JiraIssue.due_date.isnot(None),
        JiraIssue.status.in_(CLOSED_STATUS),
        JiraIssue.updated_at >= cutoff_date
    )
    
    if assignee_account_id:
        query = query.filter(JiraIssue.assignee_account_id == assignee_account_id)
    
    closed_issues = query.all()
    
    total = len(closed_issues)
    if total == 0:
        return {
            'sla_score': 100.0,
            'total_closed': 0,
            'on_time': 0,
            'late': 0,
            'message': 'Нет закрытых задач с дедлайнами'
        }
    
    on_time = 0
    late = 0
    for issue in closed_issues:
        if issue.updated_at <= issue.due_date:
            on_time += 1
        else:
            late += 1
    
    sla_score = round((on_time / total) * 100, 2)
    
    return {
        'sla_score': sla_score,
        'total_closed': total,
        'on_time': on_time,
        'late': late
    }


def calculate_deadline_stability(
    db: Session,
    project_key: str,
    assignee_account_id: Optional[str] = None,
    period_days: int = 30
) -> Dict[str, Any]:
    """
    Рассчитывает Deadline Stability — процент задач, у которых дедлайн не менялся.
    
    Примечание: Для полного расчёта нужен changelog задач.
    Пока реализуем упрощённую версию на основе наличия due_date.
    
    Args:
        db: Сессия PostgreSQL
        project_key: Ключ проекта
        assignee_account_id: ID исполнителя (если None — по всем)
        period_days: Период в днях (по умолчанию 30)
    
    Returns:
        Dict: {stability_score, total_issues, with_due_date, without_due_date}
    """
    
    cutoff_date = datetime.utcnow() - timedelta(days=period_days)
    
    query = db.query(JiraIssue).filter(
        JiraIssue.project_key == project_key,
        JiraIssue.created_at >= cutoff_date
    )
    
    if assignee_account_id:
        query = query.filter(JiraIssue.assignee_account_id == assignee_account_id)
    
    issues = query.all()
    total = len(issues)
    
    if total == 0:
        return {
            'stability_score': 100.0,
            'total_issues': 0,
            'with_due_date': 0,
            'without_due_date': 0,
            'message': 'Нет задач за период'
        }
    
    with_due_date = sum(1 for i in issues if i.due_date is not None)
    without_due_date = total - with_due_date
    
    # Чем больше задач с дедлайном, тем стабильнее (упрощённо)
    stability_score = round((with_due_date / total) * 100, 2)
    
    return {
        'stability_score': stability_score,
        'total_issues': total,
        'with_due_date': with_due_date,
        'without_due_date': without_due_date
    }


def save_sla_metrics(
    db: Session,
    project_key: str,
    sla_result: Dict[str, Any],
    stability_result: Dict[str, Any],
    period_days: int = 30
) -> None:
    """
    Сохраняет метрики SLA и Stability в project_metrics (TimescaleDB)
    """
    from app.db.timescale import timescale_engine
    from app.db.models.metrics import ProjectMetric
    from sqlalchemy.orm import Session as TimescaleSession
    
    period_end = datetime.utcnow()
    period_start = period_end - timedelta(days=period_days)
    
    # TODO: найти project_id по project_key
    project_id = 0
    
    with TimescaleSession(timescale_engine) as ts_db:
        existing = ts_db.query(ProjectMetric).filter(
            ProjectMetric.project_id == project_id,
            ProjectMetric.period_start == period_start,
            ProjectMetric.period_end == period_end
        ).first()
        
        if existing:
            existing.sla_score = sla_result['sla_score']
            existing.deadline_stability = stability_result['stability_score']
            existing.calculated_at = datetime.utcnow()
        else:
            new_metric = ProjectMetric(
                project_id=project_id,
                period_start=period_start,
                period_end=period_end,
                sla_score=sla_result['sla_score'],
                deadline_stability=stability_result['stability_score'],
                calculated_at=datetime.utcnow()
            )
            ts_db.add(new_metric)
        
        ts_db.commit()
        logger.info(f"Saved SLA metrics for project {project_key}: SLA={sla_result['sla_score']}%, Stability={stability_result['stability_score']}%")