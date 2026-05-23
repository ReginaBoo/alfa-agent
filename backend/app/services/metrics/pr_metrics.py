"""
Расчёт метрик по Pull Requests:
- PR Cycle Time (время от создания до мержа)
- Review Friction (время до первого ревью, количество итераций)
- Merge Quality (процент успешно залитых PR)
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models.normalized import GithubPullRequest, GithubPullRequestReview

logger = logging.getLogger(__name__)


def calculate_pr_cycle_time(
    db: Session,
    project_id: int,
    period_days: int = 30
) -> Dict[str, Any]:
    """
    Рассчитывает время цикла Pull Request (от создания до мержа).
    
    Cycle Time = merged_at - created_at
    
    Args:
        db: Сессия БД
        project_id: ID проекта
        period_days: Период в днях
        
    Returns:
        Dict со статистикой в часах и днях
    """
    cutoff_date = datetime.utcnow() - timedelta(days=period_days)
    
    # Получаем все залитые PR за период
    prs = db.query(GithubPullRequest).filter(
        GithubPullRequest.project_id == project_id,
        GithubPullRequest.merged == True,
        GithubPullRequest.merged_at >= cutoff_date
    ).all()
    
    if not prs:
        return {
            'avg_hours': 0,
            'avg_days': 0,
            'median_hours': 0,
            'min_hours': 0,
            'max_hours': 0,
            'total_prs': 0,
            'message': 'Нет залитых PR за период'
        }
    
    # Рассчитываем Cycle Time для каждого PR
    cycle_times_hours = []
    
    for pr in prs:
        if pr.created_at and pr.merged_at:
            delta = pr.merged_at - pr.created_at
            hours = delta.total_seconds() / 3600
            cycle_times_hours.append(hours)
    
    if not cycle_times_hours:
        return {
            'avg_hours': 0,
            'avg_days': 0,
            'median_hours': 0,
            'min_hours': 0,
            'max_hours': 0,
            'total_prs': len(prs),
            'message': 'Не удалось рассчитать Cycle Time'
        }
    
    # Статистика
    cycle_times_hours.sort()
    avg_hours = sum(cycle_times_hours) / len(cycle_times_hours)
    median_hours = cycle_times_hours[len(cycle_times_hours) // 2]
    min_hours = cycle_times_hours[0]
    max_hours = cycle_times_hours[-1]
    
    # Перцентили
    percentiles = {}
    for p in [50, 75, 90, 95]:
        idx = int(len(cycle_times_hours) * p / 100)
        if idx >= len(cycle_times_hours):
            idx = len(cycle_times_hours) - 1
        percentiles[f'p{p}'] = round(cycle_times_hours[idx], 1)
    
    logger.info(f"PR Cycle Time: avg={avg_hours:.1f}h, median={median_hours:.1f}h, prs={len(cycle_times_hours)}")
    
    return {
        'avg_hours': round(avg_hours, 1),
        'avg_days': round(avg_hours / 24, 1),
        'median_hours': round(median_hours, 1),
        'median_days': round(median_hours / 24, 1),
        'min_hours': round(min_hours, 1),
        'min_days': round(min_hours / 24, 1),
        'max_hours': round(max_hours, 1),
        'max_days': round(max_hours / 24, 1),
        'total_prs': len(cycle_times_hours),
        **percentiles
    }


def calculate_review_metrics(
    db: Session,
    project_id: int,
    period_days: int = 30
) -> Dict[str, Any]:
    """
    Рассчитывает метрики ревью:
    - Среднее время до первого ревью
    - Среднее количество ревью на PR
    - Процент_approved/changes_requested
    """
    cutoff_date = datetime.utcnow() - timedelta(days=period_days)
    
    # Получаем залитые PR с ревью
    prs = db.query(GithubPullRequest).filter(
        GithubPullRequest.project_id == project_id,
        GithubPullRequest.merged == True,
        GithubPullRequest.merged_at >= cutoff_date
    ).all()
    
    if not prs:
        return {
            'avg_first_review_hours': 0,
            'avg_reviews_per_pr': 0,
            'approval_rate': 0,
            'total_prs': 0,
            'message': 'Нет залитых PR за период'
        }
    
    pr_numbers = [pr.pr_number for pr in prs]
    
    # Получаем все ревью для этих PR
    reviews = db.query(GithubPullRequestReview).filter(
        GithubPullRequestReview.pr_id.in_(pr_numbers)
    ).all()
    
    if not reviews:
        return {
            'avg_first_review_hours': 0,
            'avg_reviews_per_pr': 0,
            'approval_rate': 0,
            'total_prs': len(prs),
            'message': 'Нет ревью за период'
        }
    
    # Группируем ревью по PR
    reviews_by_pr = {}
    for review in reviews:
        if review.pr_id not in reviews_by_pr:
            reviews_by_pr[review.pr_id] = []
        reviews_by_pr[review.pr_id].append(review)
    
    # Рассчитываем метрики
    first_review_times = []
    review_counts = []
    approved_count = 0
    changes_requested_count = 0
    
    for pr in prs:
        pr_reviews = reviews_by_pr.get(pr.pr_id, [])
        review_counts.append(len(pr_reviews))
        
        # Время до первого ревью
        if pr.created_at and pr_reviews:
            first_review = min(pr_reviews, key=lambda r: r.submitted_at or datetime.max)
            if first_review.submitted_at:
                delta = first_review.submitted_at - pr.created_at
                hours = delta.total_seconds() / 3600
                if hours >= 0:  # Исключаем аномалии
                    first_review_times.append(hours)
        
        # Считаем APPROVED / CHANGES_REQUESTED
        for review in pr_reviews:
            if review.state == 'APPROVED':
                approved_count += 1
            elif review.state == 'CHANGES_REQUESTED':
                changes_requested_count += 1
    
    # Итоговые метрики
    avg_first_review_hours = sum(first_review_times) / len(first_review_times) if first_review_times else 0
    avg_reviews_per_pr = sum(review_counts) / len(review_counts) if review_counts else 0
    total_reviewed = approved_count + changes_requested_count
    approval_rate = (approved_count / total_reviewed * 100) if total_reviewed > 0 else 0
    
    logger.info(f"Review Metrics: avg_first_review={avg_first_review_hours:.1f}h, "
                f"avg_reviews={avg_reviews_per_pr:.1f}, approval_rate={approval_rate:.1f}%")
    
    return {
        'avg_first_review_hours': round(avg_first_review_hours, 1),
        'avg_first_review_text': f"{round(avg_first_review_hours, 1)}ч",
        'avg_reviews_per_pr': round(avg_reviews_per_pr, 1),
        'approval_rate': round(approval_rate, 1),
        'total_reviews': len(reviews),
        'approved_count': approved_count,
        'changes_requested_count': changes_requested_count,
        'total_prs': len(prs)
    }


def calculate_review_friction(
    db: Session,
    project_id: int,
    period_days: int = 30
) -> Dict[str, Any]:
    """
    Рассчитывает "трение" в ревью:
    - Количество итераций (сколько раз просили изменения)
    - Процент PR с CHANGES_REQUESTED
    - Среднее количество комментиев до мержа
    """
    cutoff_date = datetime.utcnow() - timedelta(days=period_days)
    
    prs = db.query(GithubPullRequest).filter(
        GithubPullRequest.project_id == project_id,
        GithubPullRequest.merged == True,
        GithubPullRequest.merged_at >= cutoff_date
    ).all()
    
    if not prs:
        return {
            'friction_score': 0,
            'prsWithChangesRequested': 0,
            'avgReviewComments': 0,
            'total_prs': 0
        }
    
    pr_numbers = [pr.pr_number for pr in prs]
    
    reviews = db.query(GithubPullRequestReview).filter(
        GithubPullRequestReview.pr_id.in_(pr_numbers)
    ).all()
    
    # Анализируем
    prs_with_changes = set()
    total_review_comments = 0
    
    for review in reviews:
        if review.state == 'CHANGES_REQUESTED':
            prs_with_changes.add(review.pr_id)
        if review.body:
            total_review_comments += 1
    
    prs_with_changes_count = len(prs_with_changes)
    changes_ratio = prs_with_changes_count / len(prs) * 100
    avg_review_comments = total_review_comments / len(prs)
    
    # Friction Score (0-100, где 0 - идеально, 100 - максимальное трение)
    friction_score = min(100, round(changes_ratio * 2 + avg_review_comments * 5, 1))
    
    logger.info(f"Review Friction: score={friction_score}, "
                f"changes_ratio={changes_ratio:.1f}%, avg_comments={avg_review_comments:.1f}")
    
    return {
        'friction_score': friction_score,
        'prsWithChangesRequested': prs_with_changes_count,
        'changesRatio': round(changes_ratio, 1),
        'avgReviewComments': round(avg_review_comments, 1),
        'total_prs': len(prs)
    }


def calculate_stability_score(
    db: Session,
    project_id: int,
    period_days: int = 30
) -> Dict[str, Any]:
    """
    Рассчитывает Stability Score на основе CI/CD результатов.
    Пока использует данные из RawEvent (check_runs).
    
    Score = (success_checks / total_checks) * 100
    """
    from app.db.models import RawEvent
    
    cutoff_date = datetime.utcnow() - timedelta(days=period_days)
    
    # Получаем check runs события
    check_events = db.query(RawEvent).filter(
        RawEvent.source == "github",
        RawEvent.event_type == "check_run",
        RawEvent.timestamp >= cutoff_date
    ).all()
    
    if not check_events:
        return {
            'stability_score': 100,  # Нет данных = считаем стабильным
            'total_checks': 0,
            'success_checks': 0,
            'failure_checks': 0,
            'message': 'Нет данных о CI/CD'
        }
    
    # Анализируем
    total_checks = 0
    success_checks = 0
    failure_checks = 0
    
    for event in check_events:
        try:
            payload = event.payload
            if isinstance(payload, str):
                import json
                payload = json.loads(payload)
            
            stats = payload.get('stats', {})
            total_checks += stats.get('total', 0)
            success_checks += stats.get('success', 0)
            failure_checks += stats.get('failure', 0)
            
        except Exception as e:
            logger.warning(f"Error parsing check_run event: {e}")
            continue
    
    if total_checks == 0:
        return {
            'stability_score': 100,
            'total_checks': 0,
            'success_checks': 0,
            'failure_checks': 0,
            'message': 'Нет успешных проверок'
        }
    
    stability_score = (success_checks / total_checks) * 100
    
    logger.info(f"Stability Score: {stability_score:.1f}% "
                f"(success={success_checks}, failure={failure_checks}, total={total_checks})")
    
    return {
        'stability_score': round(stability_score, 1),
        'total_checks': total_checks,
        'success_checks': success_checks,
        'failure_checks': failure_checks,
        'successRate': round(success_checks / total_checks * 100, 1)
    }


def get_pr_stats_for_project(db: Session, project_id: int, period_days: int = 30) -> Dict[str, Any]:
    """
    Комплексная статистика по PR для проекта.
    Объединяет все метрики.
    """
    # Базовая статистика
    prs = db.query(GithubPullRequest).filter(
        GithubPullRequest.project_id == project_id,
        GithubPullRequest.created_at >= (datetime.utcnow() - timedelta(days=period_days))
    ).all()
    
    open_prs = [pr for pr in prs if pr.state == 'open']
    merged_prs = [pr for pr in prs if pr.merged]
    closed_prs = [pr for pr in prs if pr.state == 'closed' and not pr.merged]
    
    # Вычисляем метрики
    cycle_time = calculate_pr_cycle_time(db, project_id, period_days)
    review_metrics = calculate_review_metrics(db, project_id, period_days)
    review_friction = calculate_review_friction(db, project_id, period_days)
    stability = calculate_stability_score(db, project_id, period_days)
    
    return {
        'summary': {
            'total_prs': len(prs),
            'open_prs': len(open_prs),
            'merged_prs': len(merged_prs),
            'closed_prs': len(closed_prs)
        },
        'cycle_time': cycle_time,
        'review_metrics': review_metrics,
        'review_friction': review_friction,
        'stability': stability
    }
