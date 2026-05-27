"""
Расчёт Project Health Score (PHS) — композитной метрики здоровья проекта
"""

import logging
import math
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models import JiraIssue
from app.db.models.normalized import ProjectStatusMapping
from app.db.timescale import timescale_engine
from app.db.models.metrics import ProjectHealth
from app.services.metrics.sla_score import calculate_sla_score, calculate_deadline_stability
from app.services.metrics.workload_index import WorkloadIndexCalculator

logger = logging.getLogger(__name__)


def _get_closed_statuses_for_project(db: Session, project_key: str) -> list:
    """Получает закрытые статусы для проекта из БД"""
    mappings = db.query(ProjectStatusMapping).filter(
        ProjectStatusMapping.project_key == project_key,
        ProjectStatusMapping.is_closed == True
    ).all()
    
    if mappings:
        return [m.status_name for m in mappings]
    
    return ['Done', 'Closed', 'Resolved', 'Готово', 'Выполнено', 'Закрыто']


def _get_open_statuses_for_project(db: Session, project_key: str) -> list:
    """Получает открытые статусы для проекта из БД"""
    mappings = db.query(ProjectStatusMapping).filter(
        ProjectStatusMapping.project_key == project_key,
        ProjectStatusMapping.is_open == True
    ).all()
    
    if mappings:
        return [m.status_name for m in mappings]
    
    return ['To Do', 'In Progress', 'Open', 'Backlog', 'К выполнению', 'В работе']


def calculate_workload_balance_score(
    db: Session,
    project_key: str,
    weeks: int = 4
) -> Dict[str, Any]:
    """
    Рассчитывает Workload Balance по требованиям.
    
    Workload Balance = стандартное отклонение WI по команде.
    
    Интерпретация:
    - < 0.2: равномерно (100 баллов)
    - 0.2 - 0.5: есть отклонения (пропорционально)
    - > 0.5: критический дисбаланс (0 баллов)
    
    Returns:
        Dict: {score, balance_value, status, status_text}
    """
    calculator = WorkloadIndexCalculator(db, project_key, mode='story_points')
    team_results = calculator.calculate_for_team(weeks)
    
    if len(team_results) < 2:
        return {
            'score': 100.0,
            'balance_value': 0.0,
            'status': 'insufficient_data',
            'status_text': 'Недостаточно данных',
            'team_size': len(team_results)
        }
    
    wi_values = [r['workload_index'] for r in team_results]
    
    # Стандартное отклонение
    mean_wi = sum(wi_values) / len(wi_values)
    variance = sum((wi - mean_wi) ** 2 for wi in wi_values) / len(wi_values)
    balance_value = round(math.sqrt(variance), 2)
    
    # Конвертируем в score (0-100)
    if balance_value < 0.2:
        score = 100.0
        status = 'balanced'
        status_text = 'Нагрузка распределена равномерно'
    elif balance_value <= 0.5:
        # Линейная интерполяция: 0.2 → 100, 0.5 → 0
        score = round(100 * (1 - (balance_value - 0.2) / 0.3), 2)
        status = 'moderate'
        status_text = 'Есть некоторые отклонения'
    else:
        score = 0.0
        status = 'imbalanced'
        status_text = 'Критический дисбаланс!'
    
    return {
        'score': score,
        'balance_value': balance_value,
        'status': status,
        'status_text': status_text,
        'team_size': len(team_results),
        'team_wi': round(mean_wi, 2),
        'wi_values': wi_values
    }


def calculate_stability_score(
    db: Session,
    project_key: str,
    period_days: int = 30
) -> Dict[str, Any]:
    """
    Рассчитывает Stability Score — стабильность продукта.
    
    Учитывает:
    - Отношение багов к общему числу задач
    - Время жизни багов
    - Количество переоткрытых багов
    
    Returns:
        Dict: {score, bug_ratio, avg_bug_age_days, reopened_count}
    """
    
    cutoff_date = datetime.utcnow() - timedelta(days=period_days)
    
    # Получаем закрытые статусы
    closed_statuses = _get_closed_statuses_for_project(db, project_key)
    open_statuses = _get_open_statuses_for_project(db, project_key)
    
    # Всего задач за период
    total_issues = db.query(JiraIssue).filter(
        JiraIssue.project_key == project_key,
        JiraIssue.created_at >= cutoff_date
    ).count()
    
    if total_issues == 0:
        return {
            'score': 100.0,
            'bug_ratio': 0,
            'avg_bug_age_days': 0,
            'open_bugs': 0,
            'reopened_bugs': 0
        }
    
    # Баги за период (все)
    all_bugs = db.query(JiraIssue).filter(
        JiraIssue.project_key == project_key,
        JiraIssue.issue_type.in_(['Bug', 'Баг', 'Ошибка', 'Defect']),
        JiraIssue.created_at >= cutoff_date
    ).all()
    
    total_bugs = len(all_bugs)
    
    # Открытые баги сейчас
    open_bugs = db.query(JiraIssue).filter(
        JiraIssue.project_key == project_key,
        JiraIssue.issue_type.in_(['Bug', 'Баг', 'Ошибка', 'Defect']),
        JiraIssue.status.in_(open_statuses)
    ).count()
    
    # Среднее время жизни закрытых багов
    closed_bugs = [b for b in all_bugs if b.closed_at and b.status in closed_statuses]
    bug_ages_days = []
    for bug in closed_bugs:
        if bug.closed_at and bug.created_at:
            age_days = (bug.closed_at - bug.created_at).days
            bug_ages_days.append(age_days)
    
    avg_bug_age_days = round(sum(bug_ages_days) / len(bug_ages_days), 1) if bug_ages_days else 0
    
    # Коэффициент стабильности
    # Чем меньше багов, тем лучше (базовый фактор)
    bug_ratio = total_bugs / total_issues if total_issues > 0 else 0
    
    # Чем меньше открытых багов, тем лучше
    open_bugs_penalty = min(open_bugs / 10, 1.0) if open_bugs > 0 else 0
    
    # Чем меньше время жизни бага, тем лучше
    age_penalty = min(avg_bug_age_days / 30, 1.0) if avg_bug_age_days > 0 else 0
    
    # Итоговый score (0-100)
    base_score = (1 - bug_ratio) * 100
    open_bugs_deduction = open_bugs_penalty * 15  # максимум -15%
    age_deduction = age_penalty * 10  # максимум -10%
    
    score = max(0, base_score - open_bugs_deduction - age_deduction)
    score = round(score, 2)
    
    return {
        'score': score,
        'bug_ratio': round(bug_ratio * 100, 2),
        'total_bugs': total_bugs,
        'open_bugs': open_bugs,
        'avg_bug_age_days': avg_bug_age_days,
        'total_issues': total_issues
    }


def calculate_health_score(
    db: Session,
    project_key: str,
    period_days: int = 30,
    weights: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    """
    Рассчитывает общий Health Score проекта.
    
    Компоненты (в соответствии с требованиями):
    - SLA Score (% задач, закрытых в срок)
    - Stability Score (стабильность продукта)
    - Workload Balance (равномерность загрузки команды)
    - Deadline Stability (стабильность дедлайнов)
    
    Веса по умолчанию (можно настроить):
    - SLA: 35%
    - Stability: 30%
    - Workload Balance: 20%
    - Deadline Stability: 15%
    
    Returns:
        Dict: {health_score, status, status_text, components, thresholds}
    """
    
    if weights is None:
        weights = {
            'sla': 0.35,
            'stability': 0.30,
            'workload_balance': 0.20,
            'deadline_stability': 0.15
        }
    
    # 1. SLA Score
    sla_result = calculate_sla_score(db, project_key=project_key, period_days=period_days)
    sla_score = sla_result['sla_score']
    
    # 2. Stability Score
    stability_result = calculate_stability_score(db, project_key=project_key, period_days=period_days)
    stability_score = stability_result['score']
    
    # 3. Workload Balance
    balance_result = calculate_workload_balance_score(db, project_key=project_key)
    balance_score = balance_result['score']
    
    # 4. Deadline Stability
    deadline_result = calculate_deadline_stability(db, project_key=project_key, period_days=period_days)
    deadline_score = deadline_result['stability_score']
    
    # Расчёт Health Score
    health_score = (
        sla_score * weights['sla'] +
        stability_score * weights['stability'] +
        balance_score * weights['workload_balance'] +
        deadline_score * weights['deadline_stability']
    )
    health_score = round(health_score, 2)
    
    # Определяем статус (в соответствии с требованиями)
    if health_score >= 80:
        status = 'green'
        status_text = 'Здоров'
        icon = '✅'
    elif health_score >= 50:
        status = 'yellow'
        status_text = 'Есть риск'
        icon = '⚠️'
    else:
        status = 'red'
        status_text = 'Критично'
        icon = '🚨'
    
    # Пороговые значения для подсветки
    thresholds = {
        'sla': {'critical': 50, 'warning': 80, 'value': sla_score},
        'stability': {'critical': 50, 'warning': 80, 'value': stability_score},
        'workload_balance': {'critical': 0, 'warning': 80, 'value': balance_score},
        'deadline_stability': {'critical': 50, 'warning': 80, 'value': deadline_score}
    }
    
    logger.info(f"Health Score for {project_key}: {health_score} ({status_text})")
    
    return {
        'health_score': health_score,
        'status': status,
        'status_text': status_text,
        'icon': icon,
        'thresholds': thresholds,
        'components': {
            'sla': {
                'score': sla_score,
                'weight': weights['sla'],
                'total_closed': sla_result['total_closed'],
                'on_time': sla_result['on_time'],
                'late': sla_result['late']
            },
            'stability': {
                'score': stability_score,
                'weight': weights['stability'],
                'bug_ratio': stability_result['bug_ratio'],
                'open_bugs': stability_result['open_bugs'],
                'avg_bug_age_days': stability_result['avg_bug_age_days']
            },
            'workload_balance': {
                'score': balance_score,
                'weight': weights['workload_balance'],
                'balance_value': balance_result['balance_value'],
                'team_size': balance_result['team_size'],
                'team_wi': balance_result.get('team_wi')
            },
            'deadline_stability': {
                'score': deadline_score,
                'weight': weights['deadline_stability'],
                'total_issues': deadline_result['total_issues'],
                'changed': deadline_result.get('changed', 0),
                'unchanged': deadline_result.get('unchanged', 0)
            }
        }
    }


def get_project_health_for_card(
    db: Session,
    project_key: str,
    period_days: int = 30
) -> Dict[str, Any]:
    """
    Возвращает данные для карточки проекта на главной странице.
    
    Формат в соответствии с требованиями:
    - Загрузка (Workload Index)
    - Баги (количество открытых)
    - SLA (%)
    - Коммиты (если есть GitHub)
    - PR (если есть GitHub)
    - Ревью (если есть GitHub)
    """
    
    health = calculate_health_score(db, project_key, period_days)
    
    # Получаем открытые статусы
    open_statuses = _get_open_statuses_for_project(db, project_key)
    
    # Текущая загрузка (средний WI по команде)
    calculator = WorkloadIndexCalculator(db, project_key, mode='story_points')
    team_results = calculator.calculate_for_team()
    avg_wi = round(sum(r['workload_index'] for r in team_results) / len(team_results), 2) if team_results else 0
    wi_percent = round(min(avg_wi * 100, 200), 1)  # в процентах, макс 200%
    
    # Открытые баги
    open_bugs = db.query(JiraIssue).filter(
        JiraIssue.project_key == project_key,
        JiraIssue.issue_type.in_(['Bug', 'Баг', 'Ошибка', 'Defect']),
        JiraIssue.status.in_(open_statuses)
    ).count()
    
    # SLA
    sla = calculate_sla_score(db, project_key=project_key, period_days=period_days)
    sla_score = sla['sla_score']
    
    # Цвета для подсветки (в соответствии с требованиями)
    wi_color = 'red' if avg_wi > 1.3 else ('yellow' if avg_wi < 0.7 else 'green')
    sla_color = 'red' if sla_score < 50 else ('yellow' if sla_score < 80 else 'green')
    bugs_color = 'red' if open_bugs > 20 else ('yellow' if open_bugs > 10 else 'green')
    
    return {
        'project_key': project_key,
        'project_name': health.get('project_name', project_key),
        'health': health,
        'metrics': {
            'workload': {
                'value': wi_percent,
                'raw_value': avg_wi,
                'unit': '%',
                'status': wi_color,
                'display': f"{wi_percent}%"
            },
            'bugs': {
                'value': open_bugs,
                'unit': 'шт',
                'status': bugs_color,
                'display': str(open_bugs)
            },
            'sla': {
                'value': sla_score,
                'unit': '%',
                'status': sla_color,
                'display': f"{sla_score:.1f}%"
            }
        }
    }


def save_health_score(
    db: Session,
    project_key: str,
    health_data: Dict[str, Any],
    period_days: int = 30
) -> None:
    """Сохраняет Health Score в TimescaleDB"""
    from app.services.project_service import get_project_id_by_key
    from sqlalchemy.orm import Session as TimescaleSession
    
    period_end = datetime.utcnow()
    period_start = period_end - timedelta(days=period_days)
    
    project_id = get_project_id_by_key(db, project_key)
    
    with TimescaleSession(timescale_engine) as ts_db:
        # Проверяем, есть ли уже запись за этот период
        existing = ts_db.query(ProjectHealth).filter(
            ProjectHealth.project_id == project_id,
            ProjectHealth.period_start == period_start,
            ProjectHealth.period_end == period_end
        ).first()
        
        if existing:
            existing.health_score = health_data['health_score']
            existing.status = health_data['status']
            existing.calculated_at = datetime.utcnow()
        else:
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
        
        logger.info(f"Saved Health Score {health_data['health_score']} for project {project_id}")