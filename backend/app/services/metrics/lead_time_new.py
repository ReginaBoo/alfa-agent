"""
Расчёт Lead Time — времени от создания до закрытия задачи
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from app.db.models import JiraIssue
from app.db.models.normalized import IssueChangelog, ProjectStatusMapping
from app.services.project_status_service import ProjectStatusService

logger = logging.getLogger(__name__)


# ============================================================
# МАППИНГ СТАТУСОВ JIRA → СТАНДАРТНЫЕ ЭТАПЫ
# ============================================================

STATUS_TO_STAGE_MAPPING = {
    # Аналитика
    "to do": "Аналитика",
    "backlog": "Аналитика",
    "selected": "Аналитика",
    "new": "Аналитика",
    "open": "Аналитика",
    "к выполнению": "Аналитика",
    "аналитика": "Аналитика",
    
    # Код
    "in progress": "Код",
    "в работе": "Код",
    "код": "Код",
    
    # Ожидание ревью
    "code review": "Ожидание ревью",
    "review": "Ожидание ревью",
    "на проверке": "Ожидание ревью",
    "ожидание ревью": "Ожидание ревью",
    
    # Тестирование
    "testing": "Тестирование",
    "тестирование": "Тестирование",
    
    # Бизнес-тестирование
    "бизнес-тестирование": "Бизнес-тестирование",
    "business testing": "Бизнес-тестирование",
    
    # Внедрение
    "done": "Внедрение",
    "closed": "Внедрение",
    "resolved": "Внедрение",
    "готово": "Внедрение",
    "внедрение": "Внедрение",
    "выполнено": "Внедрение",
}

# Порядок этапов для отображения
STAGE_ORDER = [
    "Аналитика",
    "Код",
    "Ожидание ревью",
    "Тестирование",
    "Бизнес-тестирование",
    "Внедрение"
]


def map_status_to_stage(status: str) -> str:
    """
    Маппит реальный статус Jira на стандартный этап.
    Если статус не найден в маппинге - возвращает оригинальный статус.
    """
    if not status:
        return "Unknown"
    
    normalized = status.strip().lower()
    return STATUS_TO_STAGE_MAPPING.get(normalized, status)


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
    last_assignee_change = db.query(IssueChangelog).filter(
        IssueChangelog.issue_key == issue_key,
        IssueChangelog.field_name == 'assignee',
        IssueChangelog.changed_at <= point_in_time
    ).order_by(IssueChangelog.changed_at.desc()).first()
    
    if last_assignee_change and last_assignee_change.to_value:
        return last_assignee_change.to_value
    
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
    """
    
    cutoff_date = datetime.utcnow() - timedelta(days=period_days)
    closed_statuses = ProjectStatusService.get_closed_statuses(db, project_key)
    
    query = db.query(JiraIssue).filter(
        JiraIssue.project_key == project_key,
        JiraIssue.created_at >= cutoff_date
    )
    
    issues = query.all()
    
    lead_times_hours = []
    issues_analyzed = 0
    skipped_wrong_assignee = 0
    
    for issue in issues:
        if issue.closed_at:
            closed_date = issue.closed_at
        else:
            closed_date = _get_closed_at_from_changelog(db, issue.issue_key, closed_statuses)

        if not closed_date and issue.status in closed_statuses:
            closed_date = issue.updated_at

        if not closed_date:
            continue

        if closed_date < cutoff_date:
            continue
        
        if assignee_account_id:
            assignee_at_close = _get_assignee_at_time(db, issue.issue_key, closed_date)
            if assignee_at_close != assignee_account_id:
                skipped_wrong_assignee += 1
                continue
        
        if issue.created_at and closed_date:
            delta = closed_date - issue.created_at
            hours = delta.total_seconds() / 3600
            lead_times_hours.append(hours)
            issues_analyzed += 1
    
    if not lead_times_hours:
        return {
            'avg_hours': 0, 'avg_days': 0, 'median_hours': 0,
            'min_hours': 0, 'max_hours': 0, 'total_tasks': 0,
            'issues_analyzed': 0, 'skipped_wrong_assignee': skipped_wrong_assignee,
            'message': 'Нет закрытых задач за период'
        }
    
    lead_times_hours.sort()
    avg_hours = sum(lead_times_hours) / len(lead_times_hours)
    median_hours = lead_times_hours[len(lead_times_hours) // 2]
    min_hours = lead_times_hours[0]
    max_hours = lead_times_hours[-1]
    
    percentiles_result = {}
    for p in percentiles:
        idx = int(len(lead_times_hours) * p / 100)
        if idx >= len(lead_times_hours):
            idx = len(lead_times_hours) - 1
        percentiles_result[f'p{p}'] = round(lead_times_hours[idx], 1)
    
    variance = sum((h - avg_hours) ** 2 for h in lead_times_hours) / len(lead_times_hours)
    std_dev_hours = variance ** 0.5
    
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
    Рассчитывает Lead Time с разбивкой по СТАНДАРТНЫМ ЭТАПАМ.
    
    Все статусы Jira маппятся на стандартные этапы:
    - Аналитика, Код, Ожидание ревью, Тестирование, Бизнес-тестирование, Внедрение
    
    Возвращает только этапы с ненулевым временем.
    """
    cutoff_date = datetime.utcnow() - timedelta(days=period_days)
    closed_statuses = ProjectStatusService.get_closed_statuses(db, project_key)

    query = db.query(JiraIssue).filter(JiraIssue.project_key == project_key)

    if assignee_account_id:
        query = query.filter(JiraIssue.assignee_account_id == assignee_account_id)

    issues = query.all()

    # Собираем время по стандартным этапам
    stage_durations = {}

    for issue in issues:
        if issue.closed_at:
            closed_date = issue.closed_at
        else:
            closed_date = _get_closed_at_from_changelog(db, issue.issue_key, closed_statuses)

        if not closed_date:
            continue

        if closed_date < cutoff_date:
            continue

        transitions = db.query(IssueChangelog).filter(
            IssueChangelog.issue_key == issue.issue_key,
            IssueChangelog.field_name == 'status',
            IssueChangelog.changed_at <= closed_date,
            IssueChangelog.changed_at >= issue.created_at
        ).order_by(IssueChangelog.changed_at.asc()).all()

        prev_date = issue.created_at

        if transitions:
            prev_status = transitions[0].from_value or "Open"
        else:
            prev_status = issue.status or "Open"
        
        prev_stage = map_status_to_stage(prev_status)

        for transition in transitions:
            if prev_stage:
                duration = (transition.changed_at - prev_date).total_seconds() / 3600
                if duration > 0:
                    stage_durations.setdefault(prev_stage, []).append(duration)

            next_stage = map_status_to_stage(transition.to_value)
            prev_stage = next_stage
            prev_date = transition.changed_at

        if prev_stage and closed_date > prev_date:
            duration = (closed_date - prev_date).total_seconds() / 3600
            if duration > 0:
                stage_durations.setdefault(prev_stage, []).append(duration)

    # Агрегация по стандартным этапам
    result = {}

    for stage, durations in stage_durations.items():
        if not durations:
            continue
            
        durations_sorted = sorted(durations)

        result[stage] = {
            'avg_hours': round(sum(durations) / len(durations), 1),
            'avg_days': round(sum(durations) / len(durations) / 24, 1),
            'median_hours': round(durations_sorted[len(durations_sorted) // 2], 1),
            'total_hours': round(sum(durations), 1),
            'count': len(durations)
        }

    return result


def get_lead_time_status(avg_days: float) -> dict:
    if avg_days <= 2:
        return {'status': 'fast', 'status_text': 'Быстро', 'color': 'green'}
    elif avg_days <= 7:
        return {'status': 'normal', 'status_text': 'Нормально', 'color': 'blue'}
    elif avg_days <= 14:
        return {'status': 'slow', 'status_text': 'Медленно', 'color': 'yellow'}
    else:
        return {'status': 'critical', 'status_text': 'Критично', 'color': 'red'}
