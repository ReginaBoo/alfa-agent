"""
Расчёт Lead Time — времени от создания до закрытия задачи
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.db.models import JiraIssue
from app.core.statuses import CLOSED_STATUS

logger = logging.getLogger(__name__)


def calculate_lead_time(
    db: Session,
    project_key: str,
    assignee_account_id: Optional[str] = None,
    period_days: int = 30
) -> Dict[str, Any]:
    """
    Рассчитывает среднее время цикла задачи (Lead Time) в часах/днях
    """
    
    cutoff_date = datetime.utcnow() - timedelta(days=period_days)
    
    query = db.query(JiraIssue).filter(
        JiraIssue.project_key == project_key,
        JiraIssue.status.in_(CLOSED_STATUS),
        JiraIssue.updated_at >= cutoff_date
    )
    
    if assignee_account_id:
        query = query.filter(JiraIssue.assignee_account_id == assignee_account_id)
    
    closed_issues = query.all()
    
    if not closed_issues:
        return {
            'avg_hours': 0,
            'avg_days': 0,
            'median_hours': 0,
            'total_tasks': 0
        }
    
    lead_times_hours = []
    for issue in closed_issues:
        if issue.created_at and issue.updated_at:
            delta = issue.updated_at - issue.created_at
            hours = delta.total_seconds() / 3600
            lead_times_hours.append(hours)
    
    if not lead_times_hours:
        return {
            'avg_hours': 0,
            'avg_days': 0,
            'median_hours': 0,
            'total_tasks': len(closed_issues)
        }
    
    avg_hours = sum(lead_times_hours) / len(lead_times_hours)
    lead_times_hours.sort()
    median_hours = lead_times_hours[len(lead_times_hours) // 2]
    
    return {
        'avg_hours': round(avg_hours, 1),
        'avg_days': round(avg_hours / 24, 1),
        'median_hours': round(median_hours, 1),
        'total_tasks': len(closed_issues)
    }