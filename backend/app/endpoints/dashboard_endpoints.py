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
    user_project_keys = [
        p.jira_project_key for p in user_projects if p.jira_project_key]

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
        project_name = project_obj.name if project_obj else project_key

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
                weeks=1 if period == "last week" else 2
            )
            if wi:
                workload_values.append(wi)

        avg_workload = 0
        if workload_values:
            avg_workload = round(
                sum(workload_values) / len(workload_values),
                2
            )

        # Отображаем в процентах для UI (0.85 -> 85%)
        avg_workload_percent = round(avg_workload * 100)

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
        # Статус по workload: 40-85% норма, 85-100% среднее, 101-120% перегруз
        if sla_score < 70 or avg_workload_percent > 120:
            status = "error"
        elif sla_score < 85 or avg_workload_percent > 85:
            status = "warning"
        else:
            status = "success"

        # ФОРМИРУЕМ ССЫЛКУ НА JIRA
        jira_url = None
        if base_url and project_key:
            jira_url = f"{base_url}/jira/software/projects/{project_key}/summary"

        result.append({
            "id": idx,
            "name": project_name,
            "project_key": project_key,
            "project_id": project_id,
            "status": status,
            "jira_url": jira_url,
            "stats": {
                "workload": avg_workload_percent,
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

    user_project_keys = [
        p.jira_project_key for p in user_projects if p.jira_project_key]

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
    Возвращает рекурсивное дерево задач для диаграммы Гантта.

    Возвращает:
    - viewRange: границы календарной сетки
    - tasks: дерево задач с children (подзадачами)
    """
    from app.db.models.core import Project, UserProject
    from app.db.models import JiraIssue
    import re

    # Проверяем доступ к проекту
    project = db.query(Project).filter(Project.key == project_id).first()

    if not project and re.match(r'^\d+$', project_id):
        project = db.query(Project).filter(
            Project.id == int(project_id)).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    user_project = db.query(UserProject).filter(
        UserProject.project_id == project.id,
        UserProject.user_id == current_user.id
    ).first()

    if not user_project:
        raise HTTPException(status_code=403, detail="Access denied")

    # Определяем диапазон дат - РАСШИРЯЕМ!
    if period == "all":
        # Показываем задачи за последние 60 дней и следующие 90 дней вперёд
        start_date = datetime.utcnow() - timedelta(days=60)
        end_date = datetime.utcnow() + timedelta(days=90)
    else:  # last week
        start_date = datetime.utcnow() - timedelta(days=14)
        end_date = datetime.utcnow() + timedelta(days=14)

    # Получаем ВСЕ задачи проекта (включая подзадачи)
    project_key = project.jira_project_key or project.key
    all_tasks = db.query(JiraIssue).filter(
        JiraIssue.project_key == project_key,
        JiraIssue.is_deleted == False
    ).all()

    # Вычисляем ДИНАМИЧЕСКИЙ диапазон дат на основе реальных задач
    if all_tasks:
        # Находим самую раннюю дату (created_at)
        min_date = min(
            (task.created_at for task in all_tasks if task.created_at),
            default=datetime.utcnow() - timedelta(days=30)
        )
        # Находим самую позднюю дату (due_date или updated_at)
        max_date = max(
            (task.due_date or task.updated_at or datetime.utcnow() + timedelta(days=30)
             for task in all_tasks if task.due_date or task.updated_at),
            default=datetime.utcnow() + timedelta(days=30)
        )

        # Добавляем отступы: 14 дней до и 30 дней после
        start_date = min_date - timedelta(days=14)
        end_date = max_date + timedelta(days=30)

        # Но не меньше чем "последняя неделя" по дефолту
        if period == "last week":
            start_date = datetime.utcnow() - timedelta(days=14)
            end_date = datetime.utcnow() + timedelta(days=14)
    else:
        # Если задач нет, используем дефолтный диапазон
        if period == "all":
            start_date = datetime.utcnow() - timedelta(days=60)
            end_date = datetime.utcnow() + timedelta(days=90)
        else:
            start_date = datetime.utcnow() - timedelta(days=14)
            end_date = datetime.utcnow() + timedelta(days=14)

    # Разделяем на родительские задачи и подзадачи
    parent_tasks = {}
    child_tasks = []

    for task in all_tasks:
        if task.parent_issue_id:
            child_tasks.append(task)
        else:
            parent_tasks[task.id] = task

    # Строим дерево задач
    def build_task_tree(task, all_tasks_dict, child_tasks_list):
        """Рекурсивно строит дерево задач"""
        task_children = [
            ct for ct in child_tasks_list if ct.parent_issue_id == task.id]
        from math import ceil

        now = datetime.utcnow()

        status = (
        task.status.lower().strip()
        if task.status
            else ""
        )

        is_done = status in [
            "done",
            "closed",
            "resolved",
            "готово"
        ]

        # END DATE
        is_overdue = False
        overdue_since = None

        # DONE TASK
        if is_done:
            end_date = (
                task.closed_at
                or task.due_date
                or task.updated_at
                or now
            )

        # ACTIVE TASK WITH DEADLINE
        elif task.due_date:

            # ПРОСРОЧЕНА
            if task.due_date < now:
                is_overdue = True
                overdue_since = task.due_date

                # тянем до текущего дня
                end_date = now

            # ЕЩЕ НЕ ПРОСРОЧЕНА
            else:
                end_date = task.due_date

        # ACTIVE TASK WITHOUT DEADLINE
        else:
            end_date = now

        # DURATION
        duration_hours = 8

        # 1. Есть реальные worklogs Jira
        if task.time_spent and task.time_spent > 0:

            # Jira хранит секунды
            duration_hours = max(
                1,
                round(task.time_spent / 3600)
            )

        # 2. Считаем по датам
        elif (
            task.created_at
            and end_date
            and end_date >= task.created_at
        ):

            delta = end_date - task.created_at

            duration_hours = max(
                1,
                ceil(delta.total_seconds() / 3600)
            )

        # 3. Кривые даты
        else:
            duration_hours = 8

        # PROGRESS
        progress = 0

        status = (
            task.status.lower().strip()
            if task.status
            else ""
        )

        # DONE
        if status in [
            "done",
            "closed",
            "resolved",
            "готово"
        ]:
            progress = 100

        # Есть estimate + spent
        elif (
            task.time_spent
            and task.original_estimate
            and task.original_estimate > 0
        ):
            progress = min(
                99,
                round(
                    (task.time_spent / task.original_estimate) * 100
                )
            )

        # Есть просто spent
        elif task.time_spent and task.time_spent > 0:
            progress = 50

        # Есть assignee + задача старая
        elif task.assignee_name:
            progress = 50

        # Вообще ничего нет
        else:
            progress = 10

        task_data = {
            "id": str(task.id),
            "issueKey": task.issue_key,
            "task": f"{task.issue_key}: {task.summary}" if task.summary else f"Задача {task.issue_key}",
            "duration": f"{duration_hours}ч",
            "progress": progress,
            "responsible": task.assignee_name or "Не назначен",
            "start": (task.created_at or now).strftime("%Y-%m-%d"),
            "end": end_date.strftime("%Y-%m-%d"),
            "isOverdue": is_overdue,
            "overdueSince": overdue_since.strftime("%Y-%m-%d") if overdue_since else None,
            "status": task.status
        }

        if task_children:
            task_data["children"] = [
                build_task_tree(ct, all_tasks_dict, child_tasks_list)
                for ct in task_children
            ]

        return task_data

    # Формируем корневое дерево (только родительские задачи)
    task_tree = []
    for parent_id, parent_task in parent_tasks.items():
        task_tree.append(build_task_tree(
            parent_task, parent_tasks, child_tasks))

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
        project = db.query(Project).filter(
            Project.id == int(project_id)).first()

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


@router.get("/api/projects/{project_id}/cycle-time")
@router.get("/projects/{project_id}/cycle-time")
def get_project_cycle_time(
    project_id: str,
    period: str = Query("all", pattern="^(all|last week)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Данные для блока Cycle Time на Dashboard.
    """

    from app.services.metrics.lead_time import (
        calculate_lead_time,
        calculate_lead_time_by_status
    )
    from app.db.models.core import Project, UserProject
    import re

    project = db.query(Project).filter(
        Project.key == project_id
    ).first()

    if not project and re.match(r'^\d+$', project_id):
        project = db.query(Project).filter(
            Project.id == int(project_id)
        ).first()

    if not project:
        raise HTTPException(
            status_code=404,
            detail="Project not found"
        )

    user_project = db.query(UserProject).filter(
        UserProject.project_id == project.id,
        UserProject.user_id == current_user.id
    ).first()

    if not user_project:
        raise HTTPException(
            status_code=403,
            detail="Access denied"
        )

    project_key = project.jira_project_key or project.key
    # period -> days
    period_days = 3650 if period == "all" else 7

    # Общий lead time
    lead_time = calculate_lead_time(
        db=db,
        project_key=project_key,
        period_days=period_days
    )

    # Разбивка по статусам
    statuses = calculate_lead_time_by_status(
        db=db,
        project_key=project_key,
        period_days=period_days
    )

    avg_hours = lead_time.get("avg_hours", 0)

    days = int(avg_hours // 24)
    hours = int(avg_hours % 24)

    if days > 0:
        average_time_text = f"{days} дн. {hours} ч."
    else:
        average_time_text = f"{hours} ч."

    stages = []

    for idx, (status_name, data) in enumerate(statuses.items(), start=1):
        status_hours = round(data.get("avg_hours", 0), 1)

        stage = {
            "id": str(idx),
            "label": status_name,
            "hours": status_hours,
        }

        # Эвристика для bottleneck - НЕ показываем warning для Done/Closed/Resolved
        is_final_status = status_name == "Done" or status_name == "Closed" or status_name == "Resolved"
        if status_hours >= 72 and not is_final_status:
            stage["warning"] = True
            stage["tooltip"] = (
                f"Этот этап занимает в среднем "
                f"{round(status_hours / 24, 1)} дн."
            )

        stages.append(stage)

    # Самые долгие этапы — первыми (но Done/Closed всегда в конце)
    def sort_key(stage):
        # Стадии с Done/Closed/Resolved всегда в конце
        if stage["label"] in ["Done", "Closed", "Resolved"]:
            return (1, stage["hours"])  # Группа 1 (в конце), сортировка по времени
        return (0, -stage["hours"])  # Группа 0 (в начале), обратная сортировка (от большего)
    
    stages.sort(key=sort_key)

    return {
        "averageTimeText": average_time_text,
        "stages": stages
    }


@router.get("/api/projects/{project_id}/team-workload")
@router.get("/projects/{project_id}/team-workload")
def get_project_team_workload(
    project_id: int,
    period: str = Query("all", pattern="^(all|last week)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Аналитика загруженности команды (Team Workload)
    """

    from app.services.metrics.workload_index import (
        get_project_workload_detail
    )
    from app.db.models.core import Project, UserProject

    # Проверка доступа к проекту
    project = (
        db.query(Project)
        .join(UserProject, UserProject.project_id == Project.id)
        .filter(
            UserProject.user_id == current_user.id,
            Project.id == project_id
        )
        .first()
    )

    if not project:
        raise HTTPException(
            status_code=404,
            detail="Project not found"
        )

    project_key = project.key

    # Период
    weeks = 1 if period == "last week" else 4

    # Получаем аналитику
    workload_data = get_project_workload_detail(
        db=db,
        project_key=project_key,
        weeks=weeks,
        mode="story_points"
    )

    members = workload_data.get("members", [])
    balance = workload_data.get("balance", 0)

    recommendation_text = "Нагрузка распределена равномерно."

    if members:

        sorted_members = sorted(
            members,
            key=lambda x: x["workload_index"],
            reverse=True
        )

        overloaded = sorted_members[0]
        underloaded = sorted_members[-1]

        overloaded_name = (
            overloaded.get("assignee_name")
            or overloaded["assignee_account_id"]
        )

        underloaded_name = (
            underloaded.get("assignee_name")
            or underloaded["assignee_account_id"]
        )

        overloaded_wi = overloaded["workload_index"]
        underloaded_wi = underloaded["workload_index"]

        if balance > 0.5:
            recommendation_text = (
                f"Высокий дисбаланс нагрузки ({balance}). "
                f"{overloaded_name} перегружен "
                f"(WI: {overloaded_wi}), "
                f"в то время как {underloaded_name} "
                f"недогружен (WI: {underloaded_wi}). "
                f"Рекомендуется перераспределить задачи."
            )

        elif balance > 0.2:
            recommendation_text = (
                f"Есть небольшие отклонения в распределении "
                f"нагрузки (дисбаланс: {balance})."
            )

    response_members = []

    for idx, member in enumerate(members, start=1):

        response_members.append({
            "id": str(idx),
            "name": (
                member.get("assignee_name")
                or member["assignee_account_id"]
            ),
            "workloadIndex": member["workload_index"]
        })

    return {
        "calculationType": "story_points",
        "teamWorkloadBalance": balance,
        "recommendationText": recommendation_text,
        "members": response_members
    }


@router.get("/api/projects/{project_id}/team-focus")
@router.get("/projects/{project_id}/team-focus")
def get_team_focus_dashboard(
    project_id: str,
    period: str = Query(..., pattern="^(all|last week)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Team Focus donut chart.
    Показывает распределение типов задач.
    """

    from app.db.models.core import Project, UserProject
    import re

    # --------------------------------------------------
    # Проверка доступа к проекту
    # --------------------------------------------------

    project = db.query(Project).filter(
        Project.key == project_id
    ).first()

    if not project and re.match(r'^\d+$', project_id):
        project = db.query(Project).filter(
            Project.id == int(project_id)
        ).first()

    if not project:
        raise HTTPException(
            status_code=404,
            detail="Project not found"
        )

    user_project = db.query(UserProject).filter(
        UserProject.project_id == project.id,
        UserProject.user_id == current_user.id
    ).first()

    if not user_project:
        raise HTTPException(
            status_code=403,
            detail="Access denied"
        )

    # --------------------------------------------------
    # Период
    # --------------------------------------------------

    query = db.query(JiraIssue).filter(
        JiraIssue.project_key == (
            project.jira_project_key or project.key
        ),
        JiraIssue.is_deleted == False
    )

    if period == "last week":
        cutoff = datetime.utcnow() - timedelta(days=7)

        query = query.filter(
            JiraIssue.updated_at >= cutoff
        )

    issues = query.all()

    if not issues:
        return {
            "categories": []
        }

    # --------------------------------------------------
    # Категории
    # --------------------------------------------------

    categories = {
        "Новые фичи": 0,
        "Рефактор/Долг": 0,
        "Баги": 0,
        "Поддержка": 0
    }

    for issue in issues:

        issue_type = (
            issue.issue_type.lower().strip()
            if issue.issue_type
            else ""
        )

        # BUGS
        if issue_type in [
            "bug",
            "defect",
            "error",
            "ошибка",
            "баг"
        ]:
            categories["Баги"] += 1

        # TECH DEBT
        elif issue_type in [
            "refactoring",
            "technical debt",
            "tech debt",
            "chore",
            "рефакторинг"
        ]:
            categories["Рефактор/Долг"] += 1

        # SUPPORT
        elif issue_type in [
            "support",
            "maintenance",
            "поддержка"
        ]:
            categories["Поддержка"] += 1

        # FEATURES
        elif issue_type in [
            "story",
            "история",
            "task",
            "задача",
            "epic",
            "эпик",
            "feature",
            "subtask",
            "sub-task",
            "подзадача"
        ]:
            categories["Новые фичи"] += 1

        else:
            categories["Новые фичи"] += 1

    # --------------------------------------------------
    # Проценты
    # --------------------------------------------------

    total = sum(categories.values())

    result = []

    for category_name, count in categories.items():

        if count == 0:
            continue

        percent = round((count / total) * 100)

        result.append({
            "type": category_name,
            "value": percent
        })

    # Чтобы сумма была ровно 100
    total_percent = sum(item["value"] for item in result)

    if result and total_percent != 100:
        diff = 100 - total_percent
        result[0]["value"] += diff

    return {
        "categories": result
    }