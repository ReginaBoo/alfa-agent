"""
Расчёт Documentation Health Score (DHS)
Формула: DHS = 0.3×Coverage + 0.3×Freshness + 0.3×Verification + 0.1×KnowledgeDistribution
"""
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct

from app.db.models.normalized import JiraIssue, ConfluencePage, ConfluenceComment
from app.db.models.core import Project
from app.db.timescale import timescale_engine
from app.db.models.metrics import ProjectHealth
from sqlalchemy.orm import Session as TimescaleSession

logger = logging.getLogger(__name__)


def _get_project_id(db: Session, project_key: str) -> Optional[int]:
    """Вспомогательная: находит project_id по ключу"""
    project = db.query(Project).filter(Project.key == project_key).first()
    return project.id if project else None


def calculate_coverage(
    db: Session,
    project_key: str,
    period_days: int = 30
) -> Dict[str, Any]:
    """
    Coverage = % задач, имеющих ссылки на документацию.
    Проверяем: содержит ли summary/description задачи ключевые слова-ссылки
    или есть ли связанные страницы по project_key.
    """
    cutoff_date = datetime.utcnow() - timedelta(days=period_days)
    
    # Всего задач за период
    total_issues = db.query(JiraIssue).filter(
        JiraIssue.project_key == project_key,
        JiraIssue.created_at >= cutoff_date
    ).count()
    
    if total_issues == 0:
        return {'coverage_score': 100.0, 'total': 0, 'linked': 0}
    
    # Ищем задачи, в тексте которых есть ссылки на Confluence
    # Паттерн: wiki/, atlassian.net/wiki, или ключ страницы в формате [PROJ-123|page-id]
    linked_issues = db.query(JiraIssue).filter(
        JiraIssue.project_key == project_key,
        JiraIssue.created_at >= cutoff_date,
        (
            JiraIssue.summary.ilike('%wiki%') |
            JiraIssue.summary.ilike('%atlassian.net/wiki%') |
            JiraIssue.summary.ilike('%confluence%')
        )
    ).count()
    
    # Альтернатива: считаем страницы, созданные за период, как "покрывающие" проект
    pages_count = db.query(ConfluencePage).filter(
        ConfluencePage.space_key == project_key,
        ConfluencePage.created_at >= cutoff_date
    ).count()
    
    # Берём максимум из двух подходов (консервативно)
    linked = max(linked_issues, min(pages_count, total_issues))
    score = round((linked / total_issues) * 100, 2) if total_issues > 0 else 100.0
    
    return {
        'coverage_score': score,
        'total_issues': total_issues,
        'linked_count': linked,
        'pages_count': pages_count
    }


def calculate_freshness(
    db: Session,
    project_key: str,
    period_days: int = 30
) -> Dict[str, Any]:
    """
    Freshness = % страниц, обновлённых за последние N дней.
    """
    cutoff_date = datetime.utcnow() - timedelta(days=period_days)
    
    # Все страницы проекта
    total_pages = db.query(ConfluencePage).filter(
        ConfluencePage.space_key == project_key
    ).count()
    
    if total_pages == 0:
        return {'freshness_score': 100.0, 'total': 0, 'updated': 0}
    
    # Страницы, обновлённые за период
    updated_pages = db.query(ConfluencePage).filter(
        ConfluencePage.space_key == project_key,
        ConfluencePage.updated_at >= cutoff_date
    ).count()
    
    score = round((updated_pages / total_pages) * 100, 2)
    
    return {
        'freshness_score': score,
        'total_pages': total_pages,
        'updated_pages': updated_pages,
        'period_days': period_days
    }


def calculate_verification(
    db: Session,
    project_key: str,
    period_days: int = 30
) -> Dict[str, Any]:
    """
    Verification = % страниц, имеющих комментарии (признак ревью/обсуждения).
    """
    # Страницы проекта
    page_ids = db.query(ConfluencePage.id).filter(
        ConfluencePage.space_key == project_key
    ).subquery()
    
    total_pages = db.query(func.count(ConfluencePage.id)).filter(
        ConfluencePage.space_key == project_key
    ).scalar() or 0
    
    if total_pages == 0:
        return {'verification_score': 100.0, 'total': 0, 'with_comments': 0}
    
    # Страницы с хотя бы одним комментарием
    pages_with_comments = db.query(func.count(distinct(ConfluenceComment.page_id))).filter(
        ConfluenceComment.page_id.in_(page_ids)
    ).scalar() or 0
    
    score = round((pages_with_comments / total_pages) * 100, 2)
    
    return {
        'verification_score': score,
        'total_pages': total_pages,
        'pages_with_comments': pages_with_comments
    }


def calculate_knowledge_distribution(
    db: Session,
    project_key: str,
    period_days: int = 30
) -> Dict[str, Any]:
    """
    KnowledgeDistribution = равномерность распределения знаний по авторам.
    Чем меньше разброс, тем выше балл.
    Формула: 100 - (коэффициент вариации × 50), минимум 0.
    """
    cutoff_date = datetime.utcnow() - timedelta(days=period_days)
    
    # Считаем страницы на автора
    pages_per_author = db.query(
        ConfluencePage.author_id,
        func.count(ConfluencePage.id).label('page_count')
    ).filter(
        ConfluencePage.space_key == project_key,
        ConfluencePage.author_id.isnot(None),
        ConfluencePage.created_at >= cutoff_date
    ).group_by(ConfluencePage.author_id).all()
    
    if not pages_per_author:
        return {'distribution_score': 100.0, 'authors_count': 0}
    
    counts = [p[1] for p in pages_per_author]
    avg = sum(counts) / len(counts)
    
    if avg == 0:
        return {'distribution_score': 100.0, 'authors_count': len(counts)}
    
    # Коэффициент вариации
    variance = sum((x - avg) ** 2 for x in counts) / len(counts)
    cv = (variance ** 0.5) / avg if avg > 0 else 0
    
    # Преобразуем в балл: CV=0 → 100, CV=1 → 50, CV>1 → ниже
    score = max(0, 100 - cv * 50)
    
    return {
        'distribution_score': round(score, 2),
        'authors_count': len(counts),
        'pages_per_author': dict(pages_per_author),
        'cv': round(cv, 3)
    }


def calculate_doc_health_score(
    db: Session,
    project_key: str,
    period_days: int = 30
) -> Dict[str, Any]:
    """
    Основная функция: рассчитывает композитный DHS.
    """
    # Получаем компоненты
    coverage = calculate_coverage(db, project_key, period_days)
    freshness = calculate_freshness(db, project_key, period_days)
    verification = calculate_verification(db, project_key, period_days)
    distribution = calculate_knowledge_distribution(db, project_key, period_days)
    
    # Веса
    weights = {
        'coverage': 0.3,
        'freshness': 0.3,
        'verification': 0.3,
        'distribution': 0.1
    }
    
    # Расчёт итогового DHS
    dhs = (
        coverage['coverage_score'] * weights['coverage'] +
        freshness['freshness_score'] * weights['freshness'] +
        verification['verification_score'] * weights['verification'] +
        distribution['distribution_score'] * weights['distribution']
    )
    dhs = round(dhs, 2)
    
    # Определение статуса
    if dhs >= 80:
        status = 'green'
        status_text = 'Стандарт'
    elif dhs >= 50:
        status = 'yellow'
        status_text = 'Риск'
    else:
        status = 'red'
        status_text = 'Критично'
    
    return {
        'dhs_score': dhs,
        'status': status,
        'status_text': status_text,
        'components': {
            'coverage': coverage['coverage_score'],
            'freshness': freshness['freshness_score'],
            'verification': verification['verification_score'],
            'distribution': distribution['distribution_score']
        },
        'weights': weights,
        'period_days': period_days,
        'details': {
            'coverage': coverage,
            'freshness': freshness,
            'verification': verification,
            'distribution': distribution
        }
    }


def save_doc_health_score(
    db: Session,
    project_key: str,
    dhs_data: Dict[str, Any],
    period_days: int = 30
) -> bool:
    """
    Сохраняет DHS в таблицу project_health (TimescaleDB).
    Использует тот же формат, что и Project Health Score.
    """
    from app.services.metrics.utils import get_metric_period

    period_start, period_end = get_metric_period(period_days)
        
    project_id = _get_project_id(db, project_key)
    if project_id is None:
        logger.warning(f"Project '{project_key}' not found in core.projects")
        return False
    
    with TimescaleSession(timescale_engine) as ts_db:
        # Проверяем на дубликаты по периоду
        existing = ts_db.query(ProjectHealth).filter(
            ProjectHealth.project_id == project_id,
            ProjectHealth.metric_type == 'documentation_health',
            ProjectHealth.period_start == period_start,
            ProjectHealth.period_end == period_end
        ).first()
        
        if existing:
            existing.health_score = dhs_data['dhs_score']
            existing.status = dhs_data['status']
            existing.metric_type = 'documentation_health'  # ← ДОБАВИТЬ ЭТО
            existing.calculated_at = datetime.utcnow()
        else:
            new_record = ProjectHealth(
                project_id=project_id,
                period_start=period_start,
                period_end=period_end,
                health_score=dhs_data['dhs_score'],
                status=dhs_data['status'],
                metric_type='documentation_health',  # ← ДОБАВИТЬ ЭТО (важно!)
                calculated_at=datetime.utcnow()
            )
            ts_db.add(new_record)
        
        ts_db.commit()
        logger.info(
            f"Saved DHS {dhs_data['dhs_score']} ({dhs_data['status_text']}) "
            f"for project {project_key} (id={project_id})"
        )
        return True