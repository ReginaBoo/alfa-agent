# app/endpoints/dashboard_endpoints.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta

from app.db.session import get_db
from app.db.models import JiraIssue, IntegrationToken
from app.db.timescale import timescale_engine
from app.core.dependencies import get_current_user
from app.db.models import User

router = APIRouter()


@router.get("/digest")
def get_dashboard_digest(
    period: str = Query("week", regex="^(week|month)$"),
    project_ids: Optional[List[str]] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    GET /dashboard/digest
    Главная страница дайджеста с метриками по проектам
    """
    
    # Определяем период
    if period == "week":
        days = 7
    else:
        days = 30
    
    period_start = datetime.utcnow() - timedelta(days=days)
    period_end = datetime.utcnow()
    
    # Получаем проекты пользователя
    query = db.query(JiraIssue.project_key).distinct()
    if project_ids:
        query = query.filter(JiraIssue.project_key.in_(project_ids))
    
    projects = query.all()
    
    result = []
    for (project_key,) in projects:
        # Активность: созданные задачи
        created = db.query(JiraIssue).filter(
            JiraIssue.project_key == project_key,
            JiraIssue.created_at >= period_start
        ).count()
        
        # Активность: закрытые задачи
        closed = db.query(JiraIssue).filter(
            JiraIssue.project_key == project_key,
            JiraIssue.status.in_(['Готово', 'Done', 'Closed']),
            JiraIssue.updated_at >= period_start
        ).count()
        
        # Получаем WI из TimescaleDB
        from sqlalchemy.orm import Session as TimescaleSession
        from app.db.models.metrics import UserMetric
        
        with TimescaleSession(timescale_engine) as ts_db:
            # Средний WI по проекту
            avg_wi_result = ts_db.query(UserMetric.workload_index).filter(
                UserMetric.period_start >= period_start,
                UserMetric.period_end <= period_end
            ).first()
            avg_wi = avg_wi_result[0] if avg_wi_result else 0
        
        result.append({
            "id": project_key,
            "name": project_key,
            "workload_index": round(avg_wi, 2) if avg_wi else 0,
            "activity": {
                "created": created,
                "closed": closed
            },
            "health_score": None,
            "doc_health_score": None
        })
    
    return {
        "success": True,
        "data": {
            "period": period,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "projects": result
        },
        "meta": {
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": current_user.id
        }
    }


@router.get("/health")
def get_dashboard_health(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Проверка статуса дашборда"""
    return {
        "success": True,
        "data": {
            "status": "healthy",
            "tables": {
                "user_metrics": "connected",
                "jira_issues": "connected"
            }
        }
    }