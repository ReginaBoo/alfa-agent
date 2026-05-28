"""
Расчёт SLA Score и Deadline Stability
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.db.models import JiraIssue
from app.db.models.normalized import IssueChangelog, ProjectStatusMapping
from app.services.project_status_service import ProjectStatusService

logger = logging.getLogger(__name__)


def _get_closed_at_from_changelog(db: Session, issue_key: str, closed_statuses: list) -> Optional[datetime]:
    """
    Определяет дату закрытия задачи по changelog.
    Ищет первый переход в закрытый статус.
    """
    closing_event = db.query(IssueChangelog).filter(
        IssueChangelog.issue_key == issue_key,
        IssueChangelog.field_name == 'status',
        IssueChangelog.to_value.in_(closed_statuses)
    ).order_by(IssueChangelog.changed_at.asc()).first()
    
    if closing_event:
        return closing_event.changed_at
    
    return None


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
        Dict: {sla_score, total_closed, on_time, late, avg_late_days}
    """
    
    cutoff_date = datetime.utcnow() - timedelta(days=period_days)
    
    # Получаем закрытые статусы для этого проекта
    closed_statuses = ProjectStatusService.get_closed_statuses(db, project_key)
    
    # Базовый запрос — задачи с дедлайном
    query = db.query(JiraIssue).filter(
        JiraIssue.project_key == project_key,
        JiraIssue.due_date.isnot(None)
    )
    
    if assignee_account_id:
        query = query.filter(JiraIssue.assignee_account_id == assignee_account_id)
    
    issues_with_due_date = query.all()
    
    # Анализируем каждую задачу
    total = 0
    on_time = 0
    late = 0
    late_days_sum = 0
    
    for issue in issues_with_due_date:
        # Определяем дату закрытия (используем closed_at, если есть)
        if issue.closed_at:
            closed_date = issue.closed_at
        else:
            # Fallback: ищем в changelog
            closed_date = _get_closed_at_from_changelog(db, issue.issue_key, closed_statuses)
        
        # Если задача ещё не закрыта — пропускаем
        if not closed_date:
            continue
        
        # Проверяем, попадает ли закрытие в период
        if closed_date < cutoff_date:
            continue
        
        total += 1
        
        # Сравниваем дату закрытия с дедлайном
        if closed_date <= issue.due_date:
            on_time += 1
        else:
            late += 1
            late_days_sum += (closed_date - issue.due_date).days
    
    if total == 0:
        return {
            'sla_score': 100.0,
            'total_closed': 0,
            'on_time': 0,
            'late': 0,
            'avg_late_days': 0,
            'message': 'Нет закрытых задач с дедлайнами за период'
        }
    
    sla_score = round((on_time / total) * 100, 2)
    avg_late_days = round(late_days_sum / late, 1) if late > 0 else 0
    
    logger.info(f"SLA for {project_key}: {sla_score}% ({on_time}/{total}), avg late={avg_late_days}d")
    
    return {
        'sla_score': sla_score,
        'total_closed': total,
        'on_time': on_time,
        'late': late,
        'avg_late_days': avg_late_days
    }


def calculate_deadline_stability(
    db: Session,
    project_key: str,
    assignee_account_id: Optional[str] = None,
    period_days: int = 30
) -> Dict[str, Any]:
    """
    Рассчитывает Deadline Stability — процент задач, у которых дедлайн не менялся.
    
    Анализирует changelog на изменения поля 'duedate'.
    
    Args:
        db: Сессия PostgreSQL
        project_key: Ключ проекта
        assignee_account_id: ID исполнителя (если None — по всем)
        period_days: Период в днях (по умолчанию 30)
    
    Returns:
        Dict: {stability_score, total_issues, unchanged, changed, changed_count_summary}
    """
    
    cutoff_date = datetime.utcnow() - timedelta(days=period_days)
    
    # Базовый запрос задач за период
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
            'unchanged': 0,
            'changed': 0,
            'with_due_date': 0,
            'without_due_date': 0,
            'changed_count_summary': {},
            'message': 'Нет задач за период'
        }
    
    unchanged = 0
    changed = 0
    with_due_date = 0
    without_due_date = 0
    change_counts = {}
    
    for issue in issues:
        has_due_date = issue.due_date is not None
        
        if has_due_date:
            with_due_date += 1
            
            # Проверяем, было ли изменение due_date через changelog
            due_date_changes = db.query(IssueChangelog).filter(
                IssueChangelog.issue_key == issue.issue_key,
                IssueChangelog.field_name == 'duedate',
                IssueChangelog.changed_at >= cutoff_date
            ).count()
            
            if due_date_changes > 0:
                changed += 1
                change_counts[due_date_changes] = change_counts.get(due_date_changes, 0) + 1
            else:
                unchanged += 1
        else:
            without_due_date += 1
            # Задачи без дедлайна считаем стабильными (не менялся то, чего нет)
            unchanged += 1
    
    stability_score = round((unchanged / total) * 100, 2)
    
    logger.info(f"Deadline Stability for {project_key}: {stability_score}% "
                f"(unchanged={unchanged}, changed={changed}, "
                f"with_due_date={with_due_date}, without={without_due_date})")
    
    return {
        'stability_score': stability_score,
        'total_issues': total,
        'unchanged': unchanged,
        'changed': changed,
        'with_due_date': with_due_date,
        'without_due_date': without_due_date,
        'changed_count_summary': change_counts
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
    from app.services.project_service import get_project_id_by_key
    
    period_end = datetime.utcnow()
    period_start = period_end - timedelta(days=period_days)
    
    project_id = get_project_id_by_key(db, project_key)
    
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
        logger.info(f"Saved SLA metrics for project {project_key}: "
                   f"SLA={sla_result['sla_score']}%, "
                   f"Stability={stability_result['stability_score']}%")


def get_sla_status(sla_score: float) -> dict:
    """
    Возвращает статус SLA на основе процента.
    Шкала в соответствии с требованиями:
    - Красный: < 50%
    - Жёлтый: 50% - 79%
    - Зелёный: >= 80%
    """
    if sla_score < 50:
        return {'status': 'critical', 'status_text': 'Критично', 'color': 'red'}
    elif sla_score < 80:
        return {'status': 'warning', 'status_text': 'Есть риск', 'color': 'yellow'}
    else:
        return {'status': 'healthy', 'status_text': 'В норме', 'color': 'green'}