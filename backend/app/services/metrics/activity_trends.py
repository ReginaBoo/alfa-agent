"""
Расчёт Activity Trends для визуализации активности проектов
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models import JiraIssue
from app.db.models.normalized import IssueChangelog, ProjectStatusMapping
from app.services.project_status_service import ProjectStatusService

logger = logging.getLogger(__name__)


def calculate_project_activity_trend(
    db: Session,
    project_key: str,
    weeks: int = 4,
    normalize_by_team_size: bool = True
) -> Dict[str, Any]:
    """
    Рассчитывает активность проекта по неделям для Activity Trends графика.
    
    Формула: 
    Activity_raw = (1.5×StatusTransitions + 0.5×Comments + 2.0×IssuesClosed)
    
    Args:
        db: Сессия БД
        project_key: Ключ проекта
        weeks: Количество недель
        normalize_by_team_size: Нормализовать по размеру команды
    
    Returns:
        Dict с weekly_activity, baseline, baseline_ratio
    """
    
    cutoff_date = datetime.utcnow() - timedelta(weeks=weeks)
    
    # Получаем закрытые статусы для проекта
    closed_statuses = ProjectStatusService.get_closed_statuses(db, project_key)
    
    # Собираем активность по неделям
    weekly_data = {}
    
    # 1. Статус-транзиции (вес 1.5)
    transitions = db.query(
        func.date_trunc('week', IssueChangelog.changed_at).label('week'),
        func.count(IssueChangelog.id).label('count')
    ).filter(
        IssueChangelog.field_name == 'status',
        IssueChangelog.changed_at >= cutoff_date
    ).join(
        JiraIssue, IssueChangelog.issue_key == JiraIssue.issue_key
    ).filter(
        JiraIssue.project_key == project_key
    ).group_by('week').all()
    
    for week, count in transitions:
        week_key = week.isocalendar()[1]
        weekly_data[week_key] = weekly_data.get(week_key, 0) + count * 1.5
    
    # 2. Комментарии (вес 0.5)
    comments = db.query(
        func.date_trunc('week', IssueChangelog.changed_at).label('week'),
        func.count(IssueChangelog.id).label('count')
    ).filter(
        IssueChangelog.field_name == 'comment',
        IssueChangelog.changed_at >= cutoff_date
    ).join(
        JiraIssue, IssueChangelog.issue_key == JiraIssue.issue_key
    ).filter(
        JiraIssue.project_key == project_key
    ).group_by('week').all()
    
    for week, count in comments:
        week_key = week.isocalendar()[1]
        weekly_data[week_key] = weekly_data.get(week_key, 0) + count * 0.5
    
    # 3. Закрытые задачи (вес 2.0)
    closed_issues = db.query(
        func.date_trunc('week', JiraIssue.closed_at).label('week'),
        func.count(JiraIssue.id).label('count')
    ).filter(
        JiraIssue.project_key == project_key,
        JiraIssue.closed_at >= cutoff_date,
        JiraIssue.status.in_(closed_statuses)
    ).group_by('week').all()
    
    for week, count in closed_issues:
        week_key = week.isocalendar()[1]
        weekly_data[week_key] = weekly_data.get(week_key, 0) + count * 2.0
    
    # 4. Нормализация по размеру команды
    if normalize_by_team_size:
        team_size = _get_team_size(db, project_key)
        if team_size > 0:
            weekly_data = {k: v / team_size for k, v in weekly_data.items()}
    
    # 5. Расчёт Baseline (среднее за 4 недели до периода)
    baseline = sum(weekly_data.values()) / len(weekly_data) if weekly_data else 1.0
    
    # 6. Baseline Ratio (% от нормы)
    baseline_ratio = {
        week: round((value / baseline) * 100, 1) if baseline > 0 else 100
        for week, value in weekly_data.items()
    }
    
    return {
        'project_key': project_key,
        'weekly_activity': weekly_data,
        'baseline': round(baseline, 2),
        'baseline_ratio': baseline_ratio,
        'weeks': weeks
    }


def compare_projects_activity(
    db: Session,
    project_keys: List[str],
    weeks: int = 4
) -> List[Dict[str, Any]]:
    """
    Сравнивает активность нескольких проектов для графика.
    """
    results = []
    for project_key in project_keys:
        trend = calculate_project_activity_trend(db, project_key, weeks)
        results.append(trend)
    
    return results


def _get_team_size(db: Session, project_key: str) -> int:
    """Определяет размер команды проекта"""
    team_size = db.query(JiraIssue.assignee_account_id).filter(
        JiraIssue.project_key == project_key,
        JiraIssue.assignee_account_id.isnot(None)
    ).distinct().count()
    
    return max(team_size, 1)