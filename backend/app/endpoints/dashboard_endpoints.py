# app/endpoints/dashboard_endpoints.py

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi.responses import JSONResponse
import logging

from app.db.session import get_db
from app.db.models import JiraIssue, UserProject, Project
from app.db.models.normalized import GithubPullRequest, GithubCommit, GithubIssue
from app.core.dependencies import get_current_user
from app.db.models import User
from app.services.ai.providers.openrouter_provider import OpenRouterProvider
from app.services.ai.insight_service import AIInsightService
from app.core.config import settings
from app.services.cache_service import cache_service

logger = logging.getLogger(__name__)

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
    С кэшированием на 3 минуты.
    """
    
    # --- Ключ кэша ---
    cache_key = f"dashboard_digest:{current_user.id}:{period}:{','.join(sorted(project_ids or []))}"
    
    # Пробуем получить из кэша
    cached_digest = cache_service.get(cache_key)
    if cached_digest is not None:
        return cached_digest
    
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
        result = {
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
        cache_service.set(cache_key, result, expire=180)
        return result
    
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
    
    result = {
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
    
    # Сохраняем в кэш на 3 минуты
    cache_service.set(cache_key, result, expire=180)
    
    return result


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
    С кэшированием на 5 минут.
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
    
    # Ключ кэша
    cache_key = f"activity_trends:{current_user.id}:{','.join(sorted(accessible_keys))}:{weeks}"
    
    # Пробуем получить из кэша
    cached_trends = cache_service.get(cache_key)
    if cached_trends is not None:
        return cached_trends
    
    trends = compare_projects_activity(db, accessible_keys, weeks)
    
    # Сохраняем в кэш на 5 минут
    cache_service.set(cache_key, trends, expire=300)
    
    return {
        "success": True,
        "trends": trends,
        "meta": {
            "weeks": weeks,
            "user_id": current_user.id
        }
    }


@router.get("/api/projects-activity")
@router.get("/projects-activity")
def get_projects_activity(
    period: str = Query(
        ...,
        description="Период: 'Весь период' или 'Последняя неделя'"
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Возвращает активность проектов по дням.
    С кэшированием на 2 минуты.

    Формат:
    [
        {
            "date": "2026-03-01",
            "value": 15,
            "project": "Проект 1"
        }
    ]
    """

    # --- Валидация периода ---
    allowed_periods = ["Весь период", "Последняя неделя"]

    if period not in allowed_periods:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid period. Allowed: {allowed_periods}"
        )

    # --- Ключ кэша ---
    cache_key = f"projects_activity:{current_user.id}:{period}"
    
    # Пробуем получить из кэша
    cached_activity = cache_service.get(cache_key)
    if cached_activity is not None:
        return cached_activity

    # --- Получаем проекты пользователя ---
    user_projects = (
        db.query(Project)
        .join(UserProject, UserProject.project_id == Project.id)
        .filter(
            UserProject.user_id == current_user.id,
            Project.is_active == True
        )
        .all()
    )

    if not user_projects:
        result = []
    else:
        project_keys = [p.key for p in user_projects]

        # --- Фильтрация по времени ---
        query = (
            db.query(
                func.date(JiraIssue.updated_at).label("activity_date"),
                JiraIssue.project_key,
                func.count(JiraIssue.id).label("activity_count")
            )
            .filter(
                JiraIssue.project_key.in_(project_keys),
                JiraIssue.is_deleted == False
            )
        )

        # Последняя неделя
        if period == "Последняя неделя":
            week_ago = datetime.utcnow() - timedelta(days=7)
            query = query.filter(JiraIssue.updated_at >= week_ago)

        # --- Группировка ---
        query = (
            query.group_by(
                func.date(JiraIssue.updated_at),
                JiraIssue.project_key
            )
            .order_by(
                func.date(JiraIssue.updated_at)
            )
        )

        results = query.all()

        # --- Маппинг project_key -> project_name ---
        project_name_map = {
            project.key: project.name
            for project in user_projects
        }

        # --- Формируем ответ ---
        result = []
        for row in results:
            result.append({
                "date": row.activity_date.isoformat(),
                "value": row.activity_count,
                "project": project_name_map.get(row.project_key, row.project_key)
            })

    # Сохраняем в кэш на 2 минуты
    cache_service.set(cache_key, result, expire=120)

    return result

@router.get("/projects-stats")
def get_projects_stats(
    period: str = Query(..., description="Весь период | Последняя неделя"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Статистика по проектам для карточек dashboard
    С кэшированием на 2 минуты.
    """

    from app.services.metrics.sla_score import calculate_sla_score
    from app.services.metrics.workload_index import calculate_workload_index
    from app.db.models.core import Project
    from app.db.models.identity import IntegrationToken

    if period not in ["Весь период", "Последняя неделя"]:
        raise HTTPException(
            status_code=400,
            detail="period must be 'Весь период' or 'Последняя неделя'"
        )

    # Ключ кэша
    cache_key = f"projects_stats:{current_user.id}:{period}"
    
    # Пробуем получить из кэша
    cached_stats = cache_service.get(cache_key)
    if cached_stats is not None:
        return cached_stats

    cutoff_date = None
    if period == "Последняя неделя":
        cutoff_date = datetime.utcnow() - timedelta(days=7)

   
    
    # Получаем проекты пользователя из core.projects через UserProject
    user_projects = db.query(Project).join(
        UserProject, UserProject.project_id == Project.id
    ).filter(
        UserProject.user_id == current_user.id,
        Project.is_active == True
    ).all()
    
    # Извлекаем Jira project keys (jira_project_key)
    user_project_keys = [p.jira_project_key for p in user_projects if p.jira_project_key]
    
    if not user_project_keys:
        # Нет проектов у пользователя — возвращаем пустой результат
        return []
    
    # Фильтруем JiraIssue только по проектам пользователя
    projects_query = db.query(JiraIssue.project_key).filter(
        JiraIssue.project_key.in_(user_project_keys)
    ).distinct()
    
    projects = projects_query.all()
    
    # ============================================================
    # ПОЛУЧАЕМ base_url ДЛЯ ССЫЛОК
    # ============================================================
    
    base_url = None
    
    # Ищем токен текущего пользователя
    atlassian_token = db.query(IntegrationToken).filter(
        IntegrationToken.provider == "jira",
        IntegrationToken.user_id == current_user.id
    ).first()
    
    if atlassian_token and atlassian_token.instance_url:
        base_url = atlassian_token.instance_url.rstrip('/')
        print(f"[DEBUG] Found base_url from user's token: {base_url}")
    else:
        # Fallback: ищем любой токен (только для теста)
        any_token = db.query(IntegrationToken).filter(
            IntegrationToken.provider == "jira"
        ).first()
        
        if any_token and any_token.instance_url:
            base_url = any_token.instance_url.rstrip('/')
            print(f"[DEBUG] Using fallback token: {base_url}")
        else:
            print(f"[WARNING] No instance_url found")

    result = []

    for idx, (project_key,) in enumerate(projects, start=1):
        # Фильтруем задачи по проекту
        jira_query = db.query(JiraIssue).filter(
            JiraIssue.project_key == project_key
        )

        # Находим Project объект (уже есть в user_projects)
        project_obj = next(
            (p for p in user_projects if p.jira_project_key == project_key), 
            None
        )
        
        project_id = project_obj.id if project_obj else None

        if cutoff_date:
            jira_query = jira_query.filter(
                JiraIssue.updated_at >= cutoff_date
            )

        jira_issues = jira_query.all()

        if not jira_issues:
            continue

        # ---------------------------
        # WORKLOAD
        # ---------------------------
        assignees = db.query(
            JiraIssue.assignee_account_id
        ).filter(
            JiraIssue.project_key == project_key,
            JiraIssue.assignee_account_id.isnot(None)
        ).distinct().all()

        workload_values = []
        for (assignee_id,) in assignees:
            wi = calculate_workload_index(
                db=db,
                assignee_account_id=assignee_id,
                project_key=project_key,
                weeks=1 if period == "Последняя неделя" else 2
            )
            if wi:
                workload_values.append(wi)

        avg_workload = 0
        if workload_values:
            avg_workload = round(
                (sum(workload_values) / len(workload_values)) * 100
            )

        # ---------------------------
        # REVIEW TIME
        # ---------------------------
        avg_review_hours = 0
        closed_issues = [
            i for i in jira_issues
            if i.closed_at and i.created_at
        ]
        if closed_issues:
            review_times = []
            for issue in closed_issues:
                delta = issue.closed_at - issue.created_at
                review_times.append(delta.total_seconds() / 3600)
            avg_review_hours = round(
                sum(review_times) / len(review_times)
            )
        review_time_str = f"{avg_review_hours}ч"

        # ---------------------------
        # BUGS
        # ---------------------------
        bugs_count = len([
            i for i in jira_issues
            if i.issue_type
            and i.issue_type.lower() in ["bug", "defect", "error"]
        ])

        # ---------------------------
        # PR COUNT & COMMITS (GitHub)
        # ---------------------------
        from app.db.models.normalized import GithubPullRequest, GithubCommit
        
        pr_count = 0
        commits_count = 0
        
        if project_id:
            days = 30 if period == "Весь период" else 7
            cutoff_date_pr = datetime.utcnow() - timedelta(days=days)
            
            pr_count = db.query(GithubPullRequest).filter(
                GithubPullRequest.project_id == project_id,
                GithubPullRequest.created_at >= cutoff_date_pr
            ).count()
            
            commits_count = db.query(GithubCommit).filter(
                GithubCommit.project_id == project_id,
                GithubCommit.committed_at >= cutoff_date_pr
            ).count()
        
        commits_str = f"{commits_count}↑" if commits_count > 0 else "0"

        # ---------------------------
        # SLA
        # ---------------------------
        sla_result = calculate_sla_score(
            db=db,
            project_key=project_key,
            period_days=7 if period == "Последняя неделя" else 30
        )
        sla_score = round(sla_result["sla_score"])

        # ---------------------------
        # STATUS
        # ---------------------------
        if sla_score < 70 or avg_workload > 100:
            status = "error"
        elif sla_score < 85 or avg_workload > 85:
            status = "warning"
        else:
            status = "success"

        # ФОРМИРУЕМ ССЫЛКУ НА JIRA
        jira_url = None
        if base_url and project_key:
            jira_url = f"{base_url}/jira/software/projects/{project_key}/summary"

        result.append({
            "id": idx,
            "name": project_key,
            "project_id": project_id,
            "status": status,
            "jira_url": jira_url,
            "stats": {
                "workload": avg_workload,
                "reviewTime": review_time_str,
                "bugs": bugs_count,
                "prCount": pr_count,
                "commits": commits_str,
                "sla": sla_score
            }
        })

    # Сохраняем в кэш на 2 минуты
    cache_service.set(cache_key, result, expire=120)

    return result

@router.get("/teams-load")
def get_teams_load(
    period: str = Query(..., description="Весь период | Последняя неделя"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Возвращает загруженность команд для LoadChart
    """

    from app.services.metrics.workload_index import calculate_workload_index

    allowed_periods = ["Весь период", "Последняя неделя"]

    if period not in allowed_periods:
        raise HTTPException(
            status_code=400,
            detail=f"period must be one of {allowed_periods}"
        )

    weeks = 1 if period == "Последняя неделя" else 2

    # Получаем проекты пользователя
    projects = (
        db.query(Project)
        .join(UserProject, UserProject.project_id == Project.id)
        .filter(
            UserProject.user_id == current_user.id,
            Project.is_active == True
        )
        .all()
    )

    result = []

    for project in projects:

        assignees = (
            db.query(JiraIssue.assignee_account_id)
            .filter(
                JiraIssue.project_key == project.key,
                JiraIssue.assignee_account_id.isnot(None)
            )
            .distinct()
            .all()
        )

        workload_values = []

        for (assignee_id,) in assignees:

            wi = calculate_workload_index(
                db=db,
                assignee_account_id=assignee_id,
                project_key=project.key,
                weeks=weeks
            )

            if wi is not None:
                workload_values.append(wi)

        avg_load = 0.0

        if workload_values:
            avg_load = round(
                sum(workload_values) / len(workload_values),
                2
            )

        # -----------------------------
        # STATUS TYPE
        # -----------------------------

        if avg_load < 0.3:
            status_type = "underload"
            description = "Ресурсы освободились, можно подключать новые задачи"

        elif avg_load < 0.8:
            status_type = "optimal"
            description = "Команда идет строго по графику спринта"

        elif avg_load < 1.2:
            status_type = "high"
            description = "Неравномерное распределение обязанностей"

        else:
            status_type = "overload"
            description = "Критический перегруз ключевых разработчиков"

        result.append({
            "project": project.name,
            "load": avg_load,
            "statusType": status_type,
            "description": description
        })

    return result

@router.get("/ai-insights")
async def get_ai_insights(
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """
    GET /dashboard/ai-insights
    Возвращает AI-инсайты только для проектов пользователя.
    С кэшированием на 5 минут.
    """
    
    
    # Получаем проекты пользователя
    user_projects = db.query(Project).join(
        UserProject, UserProject.project_id == Project.id
    ).filter(
        UserProject.user_id == current_user.id,
        Project.is_active == True
    ).all()
    
    user_project_keys = [p.jira_project_key for p in user_projects if p.jira_project_key]
    
    # Ключ кэша с user_id
    cache_key = f"ai_insights:{current_user.id}"
    
    # Пробуем получить из кэша
    cached_insights = cache_service.get(cache_key)
    if cached_insights is not None:
        return cached_insights
    
    # Генерируем заново с фильтрацией по проектам пользователя
    provider = OpenRouterProvider(
        api_key=settings.OPENROUTER_API_KEY,
        model=settings.OPENROUTER_MODEL
    )

    service = AIInsightService(db, provider)
    
    # Передаем проекты пользователя в сервис
    insights = await service.build_insights(project_keys=user_project_keys)
    
    # Сохраняем в кэш на 5 минут
    cache_service.set(cache_key, insights, expire=300)
    
    return insights

@router.get("/projects")
def get_user_projects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Возвращает все проекты пользователя
    для dropdown на frontend.
    """

    projects = (
        db.query(Project)
        .join(UserProject, UserProject.project_id == Project.id)
        .filter(
            UserProject.user_id == current_user.id,
            Project.is_active == True
        )
        .order_by(Project.name)
        .all()
    )

    return [
        {
            "id": project.id,
            "key": project.key,
            "name": project.name,
            "avatar_url": project.avatar_url
        }
        for project in projects
    ]


@router.post("/cache/clear")
def clear_cache(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    POST /dashboard/cache/clear
    Очищает кэш для текущего пользователя.
    """
    # Очищаем кэш только для этого пользователя
    cache_service.delete_pattern(f"*:{current_user.id}:*")
    
    return {
        "success": True,
        "message": f"Cache cleared for user {current_user.id}"
    }