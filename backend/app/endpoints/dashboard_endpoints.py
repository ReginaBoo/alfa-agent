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


# ============================================================
# ЭНДПОИНТЫ ДЛЯ ДАШБОРДА (используются на фронте)
# ============================================================

# @router.get("/digest")
# def get_dashboard_digest(...):
#     """ЗАКОММЕНТИРОВАНО: не используется на фронте"""
#     ...

# @router.get("/project/{project_key}")
# def get_project_dashboard(...):
#     """ЗАКОММЕНТИРОВАНО: не используется на фронте"""
#     ...

# @router.get("/team-workload")
# def get_team_workload_summary(...):
#     """ЗАКОММЕНТИРОВАНО: не используется на фронте"""
#     ...

# @router.get("/activity-trends")
# def get_activity_trends(...):
#     """ЗАКОММЕНТИРОВАНО: не используется на фронте"""
#     ...


@router.get("/api/projects-activity")
@router.get("/projects-activity")
def get_projects_activity(
    period: str = Query(
        ...,
        description="Период: 'all' или 'last week'"
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    GET /api/projects-activity
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
    allowed_periods = ["all", "last week"]

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
        if period == "last week":
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

@router.get("/api/projects-stats")
@router.get("/projects-stats")
def get_projects_stats(
    period: str = Query(..., description="'all' или 'last week'"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    GET /api/projects-stats
    Статистика по проектам для карточек dashboard
    С кэшированием на 2 минуты.
    """

    from app.services.metrics.sla_score import calculate_sla_score
    from app.services.metrics.workload_index import calculate_workload_index
    from app.db.models.core import Project
    from app.db.models.identity import IntegrationToken

    if period not in ["all", "last week"]:
        raise HTTPException(
            status_code=400,
            detail="period must be 'all' or 'last week'"
        )

    # Ключ кэша
    cache_key = f"projects_stats:{current_user.id}:{period}"
    
    # Пробуем получить из кэша
    cached_stats = cache_service.get(cache_key)
    if cached_stats is not None:
        return cached_stats

    cutoff_date = None
    if period == "last week":
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
            days = 30 if period == "all" else 7
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
            period_days=7 if period == "last week" else 30
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

@router.get("/api/teams-load")
@router.get("/teams-load")
def get_teams_load(
    period: str = Query(..., description="'all' или 'last week'"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    GET /api/teams-load
    Возвращает загруженность команд для LoadChart
    """

    from app.services.metrics.workload_index import calculate_workload_index

    allowed_periods = ["all", "last week"]

    if period not in allowed_periods:
        raise HTTPException(
            status_code=400,
            detail=f"period must be one of {allowed_periods}"
        )

    weeks = 1 if period == "last week" else 2

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


@router.get("/api/ai-insights")
@router.get("/ai-insights")
async def get_ai_insights(
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """
    GET /api/ai-insights
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


@router.get("/api/projects")
@router.get("/projects")
def get_user_projects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Возвращает все проекты пользователя
    для dropdown на frontend.
    """
    from app.db.models.identity import IntegrationToken

    # Получаем base_url для ссылок
    base_url = None
    atlassian_token = db.query(IntegrationToken).filter(
        IntegrationToken.provider == "jira",
        IntegrationToken.user_id == current_user.id
    ).first()
    
    if atlassian_token and atlassian_token.instance_url:
        base_url = atlassian_token.instance_url.rstrip('/')
    
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

    result = []
    for project in projects:
        project_data = {
            "id": project.id,
            "key": project.key,
            "name": project.name,
            "avatar_url": project.avatar_url
        }
        
        # Добавляем ссылку на Jira, если base_url есть
        if base_url and project.jira_project_key:
            project_data["jira_url"] = f"{base_url}/jira/software/projects/{project.jira_project_key}/summary"
        
        result.append(project_data)

    return result


@router.get("/api/projects/{project_id}/tasks")
@router.get("/projects/{project_id}/tasks")
def get_project_tasks(
    project_id: str,
    period: str = Query(..., description="'all' или 'last week'"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    GET /api/projects/{project_id}/tasks
    Возвращает задачи для диаграммы Гантта.
    """
    from app.db.models.core import Project, UserProject
    from app.db.models import JiraIssue
    import re
    
    # Проверяем доступ к проекту
    # Сначала пробуем найти по key (строка)
    project = db.query(Project).filter(Project.key == project_id).first()
    
    # Если не нашли, пробуем найти по numeric ID (если project_id - число)
    if not project and re.match(r'^\d+$', project_id):
        project = db.query(Project).filter(Project.id == int(project_id)).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    user_project = db.query(UserProject).filter(
        UserProject.project_id == project.id,
        UserProject.user_id == current_user.id
    ).first()
    
    if not user_project:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Определяем диапазон дат
    if period == "all":
        start_date = datetime.utcnow() - timedelta(days=30)
        end_date = datetime.utcnow() + timedelta(days=90)
    else:  # last week
        start_date = datetime.utcnow() - timedelta(days=7)
        end_date = datetime.utcnow() + timedelta(days=14)
    
    # Получаем задачи проекта
    project_key = project.jira_project_key or project.key
    tasks_query = db.query(JiraIssue).filter(
        JiraIssue.project_key == project_key,
        JiraIssue.is_deleted == False
    )
    
    # Фильтруем по периоду
    if period == "last week":
        tasks_query = tasks_query.filter(
            JiraIssue.updated_at >= start_date
        )
    
    tasks = tasks_query.all()
    
    # Формируем структуру для Гантта
    task_tree = []
    for issue in tasks:
        task = {
            "id": str(issue.id),
            "task": issue.summary or f"Задача {issue.issue_key}",
            "duration": f"{issue.time_spent or 8}ч",
            "progress": 100 if issue.status in ["Done", "Closed", "Готово"] else 50,
            "responsible": issue.assignee_name or "Не назначен",
            "start": (issue.created_at or datetime.utcnow()).isoformat(),
            "end": (issue.due_date or datetime.utcnow()).isoformat()
        }
        task_tree.append(task)
    
    return {
        "viewRange": {
            "start": start_date.strftime("%Y-%m-%d"),
            "end": end_date.strftime("%Y-%m-%d")
        },
        "tasks": task_tree
    }


@router.get("/api/projects/{project_id}/ai-insights")
@router.get("/projects/{project_id}/ai-insights")
async def get_project_ai_insights(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """
    GET /api/projects/{project_id}/ai-insights
    Возвращает AI-инсайты для конкретного проекта.
    """
    from app.db.models.core import Project, UserProject
    import re
    
    # Проверяем доступ к проекту
    # Сначала пробуем найти по key (строка)
    project = db.query(Project).filter(Project.key == project_id).first()
    
    # Если не нашли, пробуем найти по numeric ID (если project_id - число)
    if not project and re.match(r'^\d+$', project_id):
        project = db.query(Project).filter(Project.id == int(project_id)).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    user_project = db.query(UserProject).filter(
        UserProject.project_id == project.id,
        UserProject.user_id == current_user.id
    ).first()
    
    if not user_project:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Ключ кэша
    cache_key = f"project_ai_insights:{current_user.id}:{project_id}"
    
    # Пробуем получить из кэша
    cached_insights = cache_service.get(cache_key)
    if cached_insights is not None:
        return cached_insights
    
    # Генерируем инсайты для конкретного проекта
    provider = OpenRouterProvider(
        api_key=settings.OPENROUTER_API_KEY,
        model=settings.OPENROUTER_MODEL
    )

    service = AIInsightService(db, provider)
    
    # Фильтруем по одному проекту
    project_key = project.jira_project_key or project.key
    insights = await service.build_insights(project_keys=[project_key])
    
    # Сохраняем в кэш на 5 минут
    cache_service.set(cache_key, insights, expire=300)
    
    return insights


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