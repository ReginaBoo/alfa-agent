"""
Расчёт Lead Time — времени от создания до закрытия задачи
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from app.db.models import JiraIssue
from app.db.models.normalized import IssueChangelog, ProjectStatusMapping

logger = logging.getLogger(__name__)
from app.services.project_status_service import ProjectStatusService

def normalize_status_name(status: str) -> str:
    """
    Нормализует названия статусов Jira.
    """

    if not status:
        return "Unknown"

    normalized = status.strip().lower()

    mapping = {
        "done": "Done",
        "готово": "Done",
        "closed": "Done",
        "resolved": "Done",
        "выполнено": "Done",
        "закрыто": "Done",

        "in progress": "In Progress",
        "в работе": "In Progress",

        "to do": "To Do",
        "к выполнению": "To Do",

        "backlog": "Backlog",
    }

    return mapping.get(status.lower(), status)


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


def _get_assignee_at_time(db: Session, issue_key: str, point_in_time: datetime) -> Optional[str]:
    """
    Определяет, кто был назначен на задачу в определённый момент времени.
    """
    # Ищем последнее изменение assignee до указанного момента
    last_assignee_change = db.query(IssueChangelog).filter(
        IssueChangelog.issue_key == issue_key,
        IssueChangelog.field_name == 'assignee',
        IssueChangelog.changed_at <= point_in_time
    ).order_by(IssueChangelog.changed_at.desc()).first()
    
    if last_assignee_change and last_assignee_change.to_value:
        return last_assignee_change.to_value
    
    # Если нет истории, берём текущего assignee
    issue = db.query(JiraIssue).filter(JiraIssue.issue_key == issue_key).first()
    return issue.assignee_account_id if issue else None


def calculate_lead_time(
    db: Session,
    project_key: str,
    assignee_account_id: Optional[str] = None,
    period_days: int = 30,
    percentiles: List[int] = [50, 75, 90, 95]
) -> Dict[str, Any]:
    """
    Рассчитывает время цикла задачи (Lead Time).
    
    Lead Time = время от создания задачи до её закрытия.
    
    Args:
        db: Сессия PostgreSQL
        project_key: Ключ проекта
        assignee_account_id: ID исполнителя (если None — по всем)
        period_days: Период в днях (по умолчанию 30)
        percentiles: Список перцентилей для расчёта
    
    Returns:
        Dict: Статистика по Lead Time в часах и днях
    """
    
    cutoff_date = datetime.utcnow() - timedelta(days=period_days)
    
    # Получаем закрытые статусы для проекта
    closed_statuses = ProjectStatusService.get_closed_statuses(db, project_key)
    
    # Получаем все задачи проекта за период
    query = db.query(JiraIssue).filter(
        JiraIssue.project_key == project_key,
        JiraIssue.created_at >= cutoff_date
    )
    
    issues = query.all()
    
    lead_times_hours = []
    issues_analyzed = 0
    skipped_no_closed_date = 0
    skipped_not_closed = 0
    skipped_wrong_assignee = 0
    for issue in issues:
        print("ISSUE", issue.issue_key)
        print("CURRENT STATUS", issue.status)

        # Определяем дату закрытия
        if issue.closed_at:
            closed_date = issue.closed_at
        else:
            closed_date = _get_closed_at_from_changelog(
                db,
                issue.issue_key,
                closed_statuses
            )

        # fallback
        if not closed_date and issue.status in closed_statuses:
            closed_date = issue.updated_at

        if not closed_date:
            continue

        transitions = db.query(IssueChangelog).filter(
            IssueChangelog.issue_key == issue.issue_key,
            IssueChangelog.field_name == 'status',
            IssueChangelog.changed_at <= closed_date,
            IssueChangelog.changed_at >= issue.created_at
        ).order_by(IssueChangelog.changed_at.asc()).all()

        print("TRANSITIONS", [
            (t.from_value, t.to_value, t.changed_at)
            for t in transitions
        ])
        
        # Проверяем, попадает ли закрытие в период
        if closed_date < cutoff_date:
            continue
        
        # Проверяем assignee на момент закрытия
        if assignee_account_id:
            assignee_at_close = _get_assignee_at_time(db, issue.issue_key, closed_date)
            if assignee_at_close != assignee_account_id:
                skipped_wrong_assignee += 1
                continue
        
        # Рассчитываем Lead Time
        if issue.created_at and closed_date:
            delta = closed_date - issue.created_at
            hours = delta.total_seconds() / 3600
            lead_times_hours.append(hours)
            issues_analyzed += 1
    
    if not lead_times_hours:
        return {
            'avg_hours': 0,
            'avg_days': 0,
            'median_hours': 0,
            'min_hours': 0,
            'max_hours': 0,
            'total_tasks': 0,
            'issues_analyzed': 0,
            'skipped_not_closed': skipped_not_closed,
            'skipped_wrong_assignee': skipped_wrong_assignee,
            'message': 'Нет закрытых задач за период'
        }
    
    # Основная статистика
    lead_times_hours.sort()
    avg_hours = sum(lead_times_hours) / len(lead_times_hours)
    median_hours = lead_times_hours[len(lead_times_hours) // 2]
    min_hours = lead_times_hours[0]
    max_hours = lead_times_hours[-1]
    
    # Перцентили
    percentiles_result = {}
    for p in percentiles:
        idx = int(len(lead_times_hours) * p / 100)
        if idx >= len(lead_times_hours):
            idx = len(lead_times_hours) - 1
        percentiles_result[f'p{p}'] = round(lead_times_hours[idx], 1)
    
    # Стандартное отклонение
    variance = sum((h - avg_hours) ** 2 for h in lead_times_hours) / len(lead_times_hours)
    std_dev_hours = variance ** 0.5
    
    logger.info(f"Lead Time for {project_key}: avg={avg_hours:.1f}h, "
                f"median={median_hours:.1f}h, tasks={len(lead_times_hours)}")
    
    return {
        'avg_hours': round(avg_hours, 1),
        'avg_days': round(avg_hours / 24, 1),
        'median_hours': round(median_hours, 1),
        'median_days': round(median_hours / 24, 1),
        'min_hours': round(min_hours, 1),
        'min_days': round(min_hours / 24, 1),
        'max_hours': round(max_hours, 1),
        'max_days': round(max_hours / 24, 1),
        'std_dev_hours': round(std_dev_hours, 1),
        'std_dev_days': round(std_dev_hours / 24, 1),
        'total_tasks': len(lead_times_hours),
        'issues_analyzed': issues_analyzed,
        'skipped_not_closed': skipped_not_closed,
        'skipped_wrong_assignee': skipped_wrong_assignee,
        **percentiles_result
    }


def calculate_lead_time_by_status(
    db: Session,
    project_key: str,
    assignee_account_id: Optional[str] = None,
    period_days: int = 30
) -> Dict[str, Any]:
    """
    Рассчитывает Lead Time с разбивкой по статусам (время в каждом статусе).
    """
    cutoff_date = datetime.utcnow() - timedelta(days=period_days)
    closed_statuses = ProjectStatusService.get_closed_statuses(db, project_key)

    # Получаем задачи проекта
    query = db.query(JiraIssue).filter(
        JiraIssue.project_key == project_key
    )

    if assignee_account_id:
        query = query.filter(
            JiraIssue.assignee_account_id == assignee_account_id
        )

    issues = query.all()

    status_durations = {}

    for issue in issues:

        print("ISSUE", issue.issue_key)
        print("CURRENT STATUS", issue.status)

        # Определяем дату закрытия
        if issue.closed_at:
            closed_date = issue.closed_at
        else:
            closed_date = _get_closed_at_from_changelog(
                db,
                issue.issue_key,
                closed_statuses
            )

        # fallback
        if not closed_date and issue.status in closed_statuses:
            closed_date = issue.updated_at

        # Если задача не закрыта — пропускаем
        if not closed_date:
            continue

        # Если закрыта раньше периода — пропускаем
        if closed_date < cutoff_date:
            continue

        # Получаем transitions
        transitions = db.query(IssueChangelog).filter(
            IssueChangelog.issue_key == issue.issue_key,
            IssueChangelog.field_name == 'status',
            IssueChangelog.changed_at <= closed_date,
            IssueChangelog.changed_at >= issue.created_at
        ).order_by(IssueChangelog.changed_at.asc()).all()

        print("TRANSITIONS", [
            (t.from_value, t.to_value, t.changed_at)
            for t in transitions
        ])

        # Начальная точка
        prev_date = issue.created_at

        # Начальный статус
        if transitions:
            prev_status = normalize_status_name(
                transitions[0].from_value or "Open"
            )
        else:
            prev_status = normalize_status_name(
                issue.status or "Open"
            )

        # Считаем время по статусам
        for transition in transitions:
            if prev_status:
                duration = (
                    transition.changed_at - prev_date
                ).total_seconds() / 3600

                status_durations.setdefault(prev_status, []).append(duration)

            prev_status = normalize_status_name(
                transition.to_value
            )
            prev_date = transition.changed_at

        # Последний статус до закрытия
        if prev_status and closed_date > prev_date:
            duration = (
                closed_date - prev_date
            ).total_seconds() / 3600

            status_durations.setdefault(prev_status, []).append(duration)

    # Агрегация
    result = {}

    for status, durations in status_durations.items():
        durations_sorted = sorted(durations)

        result[status] = {
            'avg_hours': round(sum(durations) / len(durations), 1),
            'avg_days': round(sum(durations) / len(durations) / 24, 1),
            'median_hours': round(
                durations_sorted[len(durations_sorted) // 2],
                1
            ),
            'total_hours': round(sum(durations), 1),
            'count': len(durations)
        }

    return result


def get_lead_time_status(avg_days: float) -> dict:
    """
    Возвращает статус Lead Time на основе среднего времени.
    (Пороги можно настроить)
    """
    if avg_days <= 2:
        return {'status': 'fast', 'status_text': 'Быстро', 'color': 'green'}
    elif avg_days <= 7:
        return {'status': 'normal', 'status_text': 'Нормально', 'color': 'blue'}
    elif avg_days <= 14:
        return {'status': 'slow', 'status_text': 'Медленно', 'color': 'yellow'}
    else:
        return {'status': 'critical', 'status_text': 'Критично', 'color': 'red'}

