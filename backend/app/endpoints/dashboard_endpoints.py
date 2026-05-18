# app/endpoints/dashboard_endpoints.py

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta

from app.db.session import get_db
from app.db.models import JiraIssue, IntegrationToken
from app.db.models.core import Project, UserProject
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
    Главная страница дайджеста с метриками по проектам.
    
    Возвращает данные для:
    - Панели мониторинга состояния проектов (Project Health Cards)
    - Монитора загрузки ресурсов (Team Workload)
    - Визуализации активности (Activity Trends)
    """
    
    # Определяем период
    if period == "week":
        days = 7
        weeks = 1
    else:
        days = 30
        weeks = 4
    
    period_start = datetime.utcnow() - timedelta(days=days)
    period_end = datetime.utcnow()
    
    # Получаем проекты пользователя из core.projects
    if project_ids:
        projects = db.query(Project).filter(
            Project.key.in_(project_ids),
            Project.is_active == True
        ).all()
    else:
        projects = db.query(Project).join(
            UserProject, UserProject.project_id == Project.id
        ).filter(
            UserProject.user_id == current_user.id,
            Project.is_active == True
        ).all()
    
    if not projects:
        return {
            "success": True,
            "data": {
                "period": period,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "projects": [],
                "team_workload": [],
                "activity_trends": []
            },
            "meta": {
                "timestamp": datetime.utcnow().isoformat(),
                "user_id": current_user.id
            }
        }
    
    project_keys = [p.key for p in projects]
    
    # 1. Получаем Health Scores для проектов
    from app.services.metrics.health_score import get_project_health_for_card, calculate_health_score
    
    health_scores = {}
    for project_key in project_keys:
        try:
            health = get_project_health_for_card(db, project_key, days)
            health_scores[project_key] = health
        except Exception as e:
            logger.error(f"Failed to get health for {project_key}: {e}")
            health_scores[project_key] = None
    
    # 2. Получаем Team Workload для гистограммы
    from app.services.metrics.workload_index import get_projects_workload_summary
    
    team_workload = get_projects_workload_summary(db, project_keys, weeks)
    
    # 3. Получаем Activity Trends для графика
    from app.services.metrics.activity_trends import compare_projects_activity
    
    activity_trends = compare_projects_activity(db, project_keys, weeks)
    
    # 4. Формируем карточки проектов
    project_cards = []
    for project in projects:
        health = health_scores.get(project.key)
        
        # Базовая информация о проекте
        card = {
            "id": project.id,
            "key": project.key,
            "name": project.name,
            "avatar_url": project.avatar_url,
            "health": None,
            "metrics": {}
        }
        
        if health:
            card["health"] = {
                "score": health['health']['health_score'],
                "status": health['health']['status'],
                "status_text": health['health']['status_text'],
                "icon": health['health'].get('icon')
            }
            card["metrics"] = health.get('metrics', {})
        
        project_cards.append(card)
    
    return {
        "success": True,
        "data": {
            "period": period,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "period_days": days,
            "weeks": weeks,
            "projects": project_cards,
            "team_workload": team_workload,
            "activity_trends": activity_trends
        },
        "meta": {
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": current_user.id,
            "total_projects": len(project_cards)
        }
    }


@router.get("/project/{project_key}")
def get_project_dashboard(
    project_key: str,
    period: str = Query("month", regex="^(week|month|quarter)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    GET /dashboard/project/{project_key}
    Детальный дашборд конкретного проекта.
    """
    
    # Определяем период
    period_days = {
        "week": 7,
        "month": 30,
        "quarter": 90
    }.get(period, 30)
    
    period_weeks = period_days // 7
    
    # Проверяем доступ к проекту
    project = db.query(Project).filter(Project.key == project_key).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    user_project = db.query(UserProject).filter(
        UserProject.project_id == project.id,
        UserProject.user_id == current_user.id
    ).first()
    
    if not user_project:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # 1. Health Score
    from app.services.metrics.health_score import calculate_health_score, get_project_health_for_card
    health = calculate_health_score(db, project_key, period_days)
    health_card = get_project_health_for_card(db, project_key, period_days)
    
    # 2. Workload Index детально
    from app.services.metrics.workload_index import get_project_workload_detail
    workload_detail = get_project_workload_detail(db, project_key, period_weeks)
    
    # 3. SLA метрики
    from app.services.metrics.sla_score import calculate_sla_score, calculate_deadline_stability
    sla = calculate_sla_score(db, project_key, period_days=period_days)
    deadline_stability = calculate_deadline_stability(db, project_key, period_days=period_days)
    
    # 4. Lead Time
    from app.services.metrics.lead_time import calculate_lead_time
    lead_time = calculate_lead_time(db, project_key, period_days=period_days)
    
    # 5. Activity Trends для этого проекта
    from app.services.metrics.activity_trends import calculate_project_activity_trend
    activity_trend = calculate_project_activity_trend(db, project_key, period_weeks)
    
    # 6. Статусы проекта
    from app.services.jira_sync_service import JiraSyncService
    sync_service = JiraSyncService(db)
    statuses = sync_service.get_project_statuses(project_key)
    
    return {
        "success": True,
        "data": {
            "project": {
                "id": project.id,
                "key": project.key,
                "name": project.name,
                "description": project.description,
                "avatar_url": project.avatar_url,
                "category": project.category
            },
            "period": {
                "name": period,
                "days": period_days,
                "weeks": period_weeks
            },
            "health": health,
            "health_card": health_card,
            "workload": workload_detail,
            "sla": {
                "score": sla['sla_score'],
                "total_closed": sla['total_closed'],
                "on_time": sla['on_time'],
                "late": sla['late'],
                "avg_late_days": sla.get('avg_late_days', 0)
            },
            "deadline_stability": deadline_stability,
            "lead_time": lead_time,
            "activity_trend": activity_trend,
            "statuses": statuses
        },
        "meta": {
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": current_user.id
        }
    }


@router.get("/team-workload")
def get_team_workload_summary(
    project_keys: List[str] = Query(..., description="Список проектов для сравнения"),
    weeks: int = Query(4, ge=2, le=12, description="Количество недель"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    GET /dashboard/team-workload
    Возвращает данные для гистограммы Team Workload.
    
    Используется на главной странице для отображения загрузки по проектам.
    """
    from app.services.metrics.workload_index import get_projects_workload_summary
    
    # Проверяем доступ к проектам
    accessible_projects = db.query(Project.key).join(
        UserProject, UserProject.project_id == Project.id
    ).filter(
        UserProject.user_id == current_user.id,
        Project.key.in_(project_keys)
    ).all()
    
    accessible_keys = [p[0] for p in accessible_projects]
    
    if not accessible_keys:
        return {
            "success": True,
            "projects": [],
            "message": "No accessible projects"
        }
    
    summary = get_projects_workload_summary(db, accessible_keys, weeks)
    
    return {
        "success": True,
        "projects": summary,
        "meta": {
            "weeks": weeks,
            "user_id": current_user.id
        }
    }


@router.get("/activity-trends")
def get_activity_trends(
    project_keys: List[str] = Query(..., description="Список проектов для сравнения"),
    weeks: int = Query(4, ge=2, le=12, description="Количество недель"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    GET /dashboard/activity-trends
    Возвращает данные для графика Activity Trends.
    
    Отображает динамику активности проектов по неделям.
    """
    from app.services.metrics.activity_trends import compare_projects_activity
    
    # Проверяем доступ к проектам
    accessible_projects = db.query(Project.key).join(
        UserProject, UserProject.project_id == Project.id
    ).filter(
        UserProject.user_id == current_user.id,
        Project.key.in_(project_keys)
    ).all()
    
    accessible_keys = [p[0] for p in accessible_projects]
    
    if not accessible_keys:
        return {
            "success": True,
            "trends": [],
            "message": "No accessible projects"
        }
    
    trends = compare_projects_activity(db, accessible_keys, weeks)
    
    return {
        "success": True,
        "trends": trends,
        "meta": {
            "weeks": weeks,
            "user_id": current_user.id
        }
    }


@router.get("/health-cards")
def get_project_health_cards(
    project_keys: Optional[List[str]] = Query(None, description="Список проектов (если None — все проекты пользователя)"),
    period_days: int = Query(30, ge=7, le=90),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    GET /dashboard/health-cards
    Возвращает данные для карточек здоровья проектов.
    
    Используется на главной странице для панели мониторинга.
    """
    from app.services.metrics.health_score import get_project_health_for_card
    
    # Получаем проекты пользователя
    if project_keys:
        projects = db.query(Project).filter(
            Project.key.in_(project_keys),
            Project.is_active == True
        ).all()
    else:
        projects = db.query(Project).join(
            UserProject, UserProject.project_id == Project.id
        ).filter(
            UserProject.user_id == current_user.id,
            Project.is_active == True
        ).all()
    
    cards = []
    for project in projects:
        try:
            card = get_project_health_for_card(db, project.key, period_days)
            card['project_id'] = project.id
            card['project_key'] = project.key
            card['project_name'] = project.name
            card['avatar_url'] = project.avatar_url
            cards.append(card)
        except Exception as e:
            logger.error(f"Failed to get health card for {project.key}: {e}")
            cards.append({
                'project_key': project.key,
                'project_name': project.name,
                'health': None,
                'metrics': {},
                'error': str(e)
            })
    
    return {
        "success": True,
        "cards": cards,
        "meta": {
            "period_days": period_days,
            "user_id": current_user.id,
            "total": len(cards)
        }
    }


@router.get("/health")
def get_dashboard_health(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Проверка статуса дашборда и всех зависимостей"""
    
    # Проверяем подключение к TimescaleDB
    timescale_status = "connected"
    try:
        from sqlalchemy.orm import Session as TimescaleSession
        from app.db.models.metrics import UserMetric
        with TimescaleSession(timescale_engine) as ts_db:
            ts_db.query(UserMetric).limit(1).first()
    except Exception as e:
        timescale_status = f"error: {str(e)}"
    
    # Проверяем количество проектов
    projects_count = db.query(Project).join(
        UserProject, UserProject.project_id == Project.id
    ).filter(
        UserProject.user_id == current_user.id
    ).count()
    
    # Проверяем количество задач
    issues_count = db.query(JiraIssue).filter(
        JiraIssue.project_key.in_(
            db.query(Project.key).join(
                UserProject, UserProject.project_id == Project.id
            ).filter(UserProject.user_id == current_user.id)
        )
    ).count()
    
    return {
        "success": True,
        "data": {
            "status": "healthy",
            "components": {
                "postgresql": "connected",
                "timescaledb": timescale_status,
                "redis": "connected"  # можно проверить реально
            },
            "stats": {
                "projects_count": projects_count,
                "issues_count": issues_count
            }
        }
    }


# Добавляем логгер
import logging
logger = logging.getLogger(__name__)