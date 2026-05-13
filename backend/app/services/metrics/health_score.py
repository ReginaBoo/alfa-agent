"""
Расчёт Project Health Score
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.db.models import JiraIssue, IntegrationToken
from app.db.models.core import Project  # ← импорт модели проекта
from app.db.timescale import timescale_engine
from app.db.models.metrics import ProjectHealth
from app.core.statuses import CLOSED_STATUS
from sqlalchemy.orm import Session as TimescaleSession

logger = logging.getLogger(__name__)


def calculate_stability_score(
    db: Session,
    project_key: str,
    period_days: int = 30
) -> float:
    """
    Stability Score = (1 - баги / всего задач) × 100
    """
    cutoff_date = datetime.utcnow() - timedelta(days=period_days)
    
    total = db.query(JiraIssue).filter(
        JiraIssue.project_key == project_key,
        JiraIssue.created_at >= cutoff_date
    ).count()
    
    if total == 0:
        return 100.0
    
    bugs = db.query(JiraIssue).filter(
        JiraIssue.project_key == project_key,
        JiraIssue.issue_type.in_(['Bug', 'Баг', 'Ошибка', 'Defect']),
        JiraIssue.created_at >= cutoff_date
    ).count()
    
    return round((1 - bugs / total) * 100, 2)


def calculate_workload_balance(
    db: Session,
    project_key: str,
    period_days: int = 30
) -> float:
    """
    Workload Balance — равномерность загрузки команды.
    Чем меньше разброс задач между исполнителями, тем выше балл.
    """
    from sqlalchemy import func
    
    cutoff_date = datetime.utcnow() - timedelta(days=period_days)
    
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
    
    if max_tasks == 0:
        return 100.0
    
    # Коэффициент вариации: чем меньше разброс, тем ближе к 100
    avg = sum(counts) / len(counts)
    if avg == 0:
        return 100.0
    
    variance = sum((x - avg) ** 2 for x in counts) / len(counts)
    cv = (variance ** 0.5) / avg  # коэффициент вариации
    
    # Преобразуем в балл: CV=0 → 100, CV=1 → 50, CV>1 → ниже
    balance = max(0, 100 - cv * 50)
    return round(balance, 2)


def calculate_deadline_stability(
    db: Session,
    project_key: str,
    period_days: int = 30
) -> Dict[str, Any]:
    """
    Deadline Stability — процент задач с установленным дедлайном.
    В будущем можно анализировать changelog на предмет сдвигов дедлайнов.
    """
    cutoff_date = datetime.utcnow() - timedelta(days=period_days)
    
    issues = db.query(JiraIssue).filter(
        JiraIssue.project_key == project_key,
        JiraIssue.created_at >= cutoff_date
    ).all()
    
    total = len(issues)
    if total == 0:
        return {'stability_score': 100.0, 'total': 0, 'with_due': 0}
    
    with_due = sum(1 for i in issues if i.due_date is not None)
    score = round((with_due / total) * 100, 2)
    
    return {
        'stability_score': score,
        'total': total,
        'with_due': with_due,
        'without_due': total - with_due
    }


def calculate_health_score(
    db: Session,
    project_key: str,
    period_days: int = 30
) -> Dict[str, Any]:
    """
    Основная функция расчёта композитного Health Score.
    """
    from app.services.metrics.sla_score import calculate_sla_score
    
    # Получаем компоненты
    sla_result = calculate_sla_score(db, project_key=project_key, period_days=period_days)
    stability = calculate_stability_score(db, project_key=project_key, period_days=period_days)
    workload_balance = calculate_workload_balance(db, project_key=project_key, period_days=period_days)
    deadline_result = calculate_deadline_stability(db, project_key=project_key, period_days=period_days)
    
    # Веса
    weights = {
        'sla': 0.30,
        'stability': 0.30,
        'workload_balance': 0.30,
        'deadline_stability': 0.10
    }
    
    # Расчёт итогового балла
    health_score = (
        sla_result['sla_score'] * weights['sla'] +
        stability * weights['stability'] +
        workload_balance * weights['workload_balance'] +
        deadline_result['stability_score'] * weights['deadline_stability']
    )
    health_score = round(health_score, 2)
    
    # Определение статуса
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
            'sla_score': sla_result['sla_score'],
            'stability_score': stability,
            'workload_balance': workload_balance,
            'deadline_stability': deadline_result['stability_score']
        },
        'weights': weights,
        'period_days': period_days
    }


def _get_project_id(db: Session, project_key: str) -> Optional[int]:
    """Вспомогательная функция: получает project_id по ключу"""
    project = db.query(Project).filter(Project.key == project_key).first()
    return project.id if project else None


def save_health_score(
    db: Session,
    project_key: str,
    health_data: Dict[str, Any],
    period_days: int = 30
) -> bool:
    """
    Сохраняет Health Score в таблицу project_health (TimescaleDB).
    Returns True если успешно, False если не найден project_id.
    """
    period_end = datetime.utcnow()
    period_start = period_end - timedelta(days=period_days)
    
    project_id = _get_project_id(db, project_key)
    if project_id is None:
        logger.warning(f"Project not found for key: {project_key}")
        return False
    
    with TimescaleSession(timescale_engine) as ts_db:
        # Проверяем, есть ли запись за этот период
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
            new_record = ProjectHealth(
                project_id=project_id,
                period_start=period_start,
                period_end=period_end,
                health_score=health_data['health_score'],
                status=health_data['status'],
                calculated_at=datetime.utcnow()
            )
            ts_db.add(new_record)
        
        ts_db.commit()
        logger.info(
            f"Saved Health Score {health_data['health_score']} "
            f"({health_data['status_text']}) for project {project_key} (id={project_id})"
        )
        return True