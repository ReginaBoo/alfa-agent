# app/endpoints/metrics_endpoints.py

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.db.models import User, JiraIssue
from app.workers.queues import calculate_metrics_queue
from app.workers.tasks import calculate_metrics_task

router = APIRouter()


@router.post("/calculate/{project_key}")
def calculate_metrics(
    project_key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Запускает пересчёт метрик для указанного проекта (синхронно).
    """
    from app.services.metrics.workload_index import calculate_workload_index
    from app.services.metrics.sla_score import calculate_sla_score
    from app.services.metrics.health_score import calculate_health_score, save_health_score
    from app.db.models import JiraIssue
    
    assignee = db.query(JiraIssue.assignee_account_id).filter(
        JiraIssue.project_key == project_key,
        JiraIssue.assignee_account_id.isnot(None)
    ).first()
    
    if not assignee:
        raise HTTPException(status_code=404, detail=f"No assignee found for project {project_key}")
    
    assignee_id = assignee[0]
    
    wi = calculate_workload_index(db, assignee_id, project_key, weeks=2)
    sla = calculate_sla_score(db, project_key=project_key)
    health = calculate_health_score(db, project_key=project_key)
    save_health_score(db, project_key, health)
    
    return {
        "success": True,
        "data": {
            "project_key": project_key,
            "workload_index": wi,
            "sla_score": sla['sla_score'],
            "health_score": health['health_score'],
            "health_status": health['status_text']
        }
    }


@router.post("/calculate-async/{project_key}")
def calculate_metrics_async(
    project_key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Запускает пересчёт метрик для указанного проекта (асинхронно через очередь).
    Возвращает job_id для отслеживания статуса.
    """
    try:
        job = calculate_metrics_queue.enqueue(
            calculate_metrics_task,
            args=(current_user.id, project_key),
            job_timeout="120s",
            result_ttl=3600,
            failure_ttl=3600
        )
        
        return {
            "success": True,
            "message": f"Metrics calculation for project {project_key} queued",
            "data": {
                "job_id": job.id,
                "status": "queued",
                "project_key": project_key
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to queue metrics calculation: {str(e)}")


@router.post("/calculate-all-async")
def calculate_all_metrics_async(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Запускает пересчёт метрик для всех проектов (асинхронно).
    """
    projects = db.query(JiraIssue.project_key).distinct().all()
    
    jobs = []
    for (project_key,) in projects:
        job = calculate_metrics_queue.enqueue(
            calculate_metrics_task,
            args=(current_user.id, project_key),
            job_timeout="120s",
            result_ttl=3600,
            failure_ttl=3600
        )
        jobs.append({
            "project_key": project_key,
            "job_id": job.id
        })
    
    return {
        "success": True,
        "message": f"Metrics calculation queued for {len(jobs)} projects",
        "data": {
            "jobs": jobs
        }
    }


@router.get("/progress/{issue_key}")
def get_issue_progress(
    issue_key: str,
    instance_name: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Возвращает прогресс задачи в процентах
    Прогресс = time_spent / original_estimate * 100
    """
    from app.db.models import JiraIssue
    
    issue = db.query(JiraIssue).filter(JiraIssue.issue_key == issue_key).first()
    
    if not issue:
        raise HTTPException(status_code=404, detail=f"Issue {issue_key} not found")
    
    progress = 0
    if issue.original_estimate and issue.original_estimate > 0:
        progress = min(round((issue.time_spent or 0) / issue.original_estimate * 100, 1), 100)
    
    return {
        "success": True,
        "data": {
            "issue_key": issue_key,
            "original_estimate_hours": issue.original_estimate,
            "time_spent_hours": issue.time_spent,
            "progress_percent": progress,
            "status": issue.status
        }
    }


@router.get("/lead-time/{project_key}")
def get_lead_time(
    project_key: str,
    assignee_account_id: Optional[str] = Query(None),
    period_days: int = Query(30, ge=1, le=90),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Возвращает среднее время цикла задачи (Lead Time) в часах
    """
    from app.services.metrics.lead_time import calculate_lead_time
    
    result = calculate_lead_time(
        db=db,
        project_key=project_key,
        assignee_account_id=assignee_account_id,
        period_days=period_days
    )
    
    return {
        "success": True,
        "data": result,
        "project_key": project_key
    }

@router.get("/task-plan/{project_key}")
def get_task_plan(
    project_key: str,
    assignee_account_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Возвращает план по задачам проекта:
    - Оценка (original_estimate)
    - Затрачено (time_spent)
    - Осталось (remaining_estimate)
    - Прогресс (%)
    """
    from app.db.models import JiraIssue
    
    query = db.query(JiraIssue).filter(
        JiraIssue.project_key == project_key
    )
    
    if assignee_account_id:
        query = query.filter(JiraIssue.assignee_account_id == assignee_account_id)
    
    issues = query.all()
    
    result = []
    for issue in issues:
        progress = 0
        if issue.original_estimate and issue.original_estimate > 0:
            progress = min(round((issue.time_spent or 0) / issue.original_estimate * 100, 1), 100)
        
        result.append({
            "issue_key": issue.issue_key,
            "summary": issue.summary,
            "status": issue.status,
            "original_estimate_hours": issue.original_estimate,
            "time_spent_hours": issue.time_spent,
            "remaining_estimate_hours": issue.remaining_estimate,
            "progress_percent": progress
        })
    
    return {
        "success": True,
        "data": result,
        "total": len(result),
        "project_key": project_key
    }


@router.get("/focus/{project_key}")
def get_team_focus(
    project_key: str,
    period_days: int = Query(30, ge=1, le=90),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Возвращает фокусировку команды:
    - Новые фичи (Story, Task)
    - Рефакторинг/Долг
    - Баги (Bug)
    """
    from app.db.models import JiraIssue
    from datetime import datetime, timedelta
    
    cutoff_date = datetime.utcnow() - timedelta(days=period_days)
    
    issues = db.query(JiraIssue).filter(
        JiraIssue.project_key == project_key,
        JiraIssue.created_at >= cutoff_date
    ).all()
    
    total = len(issues)
    
    # Категоризация по типам задач
    categories = {
        "new_features": 0,      # Story, Task, Epic
        "refactoring": 0,       # Refactoring, Technical debt
        "bugs": 0               # Bug
    }
    
    for issue in issues:
        issue_type = issue.issue_type.lower() if issue.issue_type else ""
        
        if issue_type in ["story", "task", "epic", "feature"]:
            categories["new_features"] += 1
        elif issue_type in ["bug", "defect", "error"]:
            categories["bugs"] += 1
        elif issue_type in ["refactoring", "technical debt", "chore"]:
            categories["refactoring"] += 1
        else:
            # По умолчанию считаем новой фичей
            categories["new_features"] += 1
    
    # Расчёт процентов
    result = {}
    for key, count in categories.items():
        result[key] = {
            "count": count,
            "percent": round(count / total * 100, 1) if total > 0 else 0
        }
    
    result["total_tasks"] = total
    result["period_days"] = period_days
    
    return {
        "success": True,
        "data": result,
        "project_key": project_key
    }

@router.get("/workload/{project_key}")
def get_workload_index(
    project_key: str,
    assignee_account_id: Optional[str] = Query(None),
    weeks: int = Query(2, ge=1, le=4),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Возвращает Workload Index для сотрудников проекта.
    
    WI < 0.7 — недогруз (синий)
    WI 0.7-1.1 — оптимально (зелёный)
    WI > 1.1 — перегруз (красный)
    """
    from app.services.metrics.workload_index import calculate_workload_index, get_workload_status
    from app.db.models import JiraIssue
    
    query = db.query(JiraIssue.assignee_account_id).filter(
        JiraIssue.project_key == project_key,
        JiraIssue.assignee_account_id.isnot(None)
    ).distinct()
    
    if assignee_account_id:
        query = query.filter(JiraIssue.assignee_account_id == assignee_account_id)
    
    assignees = query.all()
    
    if not assignees:
        raise HTTPException(status_code=404, detail=f"No assignees found for project {project_key}")
    
    result = []
    for (assignee_id,) in assignees:
        wi = calculate_workload_index(db, assignee_id, project_key, weeks)
        status_info = get_workload_status(wi) if wi else {}
        
        result.append({
            "assignee_account_id": assignee_id,
            "workload_index": wi,
            "status": status_info.get('status'),
            "status_text": status_info.get('status_text'),
            "color": status_info.get('color')
        })
    
    # Сортируем по убыванию нагрузки
    result.sort(key=lambda x: x['workload_index'] or 0, reverse=True)
    
    return {
        "success": True,
        "data": result,
        "project_key": project_key,
        "weeks": weeks
    }

@router.get("/activity/{project_key}")
def get_activity_score(
    project_key: str,
    assignee_account_id: Optional[str] = Query(None),
    period_days: int = Query(30, ge=7, le=90),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Возвращает Activity Score сотрудников (0-100).
    
    Компоненты:
    - Закрытые задачи (макс 50 баллов)
    - Обновления задач (макс 30 баллов)
    - Созданные задачи (макс 20 баллов)
    """
    from app.services.metrics.activity_score import calculate_activity_score
    from app.db.models import JiraIssue
    
    query = db.query(JiraIssue.assignee_account_id).filter(
        JiraIssue.project_key == project_key,
        JiraIssue.assignee_account_id.isnot(None)
    ).distinct()
    
    if assignee_account_id:
        query = query.filter(JiraIssue.assignee_account_id == assignee_account_id)
    
    assignees = query.all()
    
    if not assignees:
        raise HTTPException(status_code=404, detail=f"No assignees found for project {project_key}")
    
    result = []
    for (assignee_id,) in assignees:
        activity = calculate_activity_score(db, assignee_id, project_key, period_days)
        
        # Определяем уровень активности
        if activity >= 70:
            level = "high"
            level_text = "Высокая"
        elif activity >= 40:
            level = "medium"
            level_text = "Средняя"
        else:
            level = "low"
            level_text = "Низкая"
        
        result.append({
            "assignee_account_id": assignee_id,
            "activity_score": activity,
            "level": level,
            "level_text": level_text
        })
    
    # Сортируем по убыванию активности
    result.sort(key=lambda x: x['activity_score'], reverse=True)
    
    return {
        "success": True,
        "data": result,
        "project_key": project_key,
        "period_days": period_days
    }


@router.get("/sla/{project_key}")
def get_sla_score(
    project_key: str,
    assignee_account_id: Optional[str] = Query(None),
    period_days: int = Query(30, ge=7, le=90),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Возвращает SLA Score — процент задач, закрытых в срок.
    """
    from app.services.metrics.sla_score import calculate_sla_score
    
    result = calculate_sla_score(
        db=db,
        project_key=project_key,
        assignee_account_id=assignee_account_id,
        period_days=period_days
    )
    
    # Определяем уровень SLA
    sla = result['sla_score']
    if sla >= 90:
        level = "excellent"
        level_text = "Отлично"
    elif sla >= 70:
        level = "good"
        level_text = "Хорошо"
    elif sla >= 50:
        level = "warning"
        level_text = "Требует внимания"
    else:
        level = "critical"
        level_text = "Критично"
    
    return {
        "success": True,
        "data": {
            "sla_score": sla,
            "level": level,
            "level_text": level_text,
            "total_closed": result['total_closed'],
            "on_time": result['on_time'],
            "late": result['late']
        },
        "project_key": project_key,
        "period_days": period_days
    }


@router.get("/health/{project_key}")
def get_project_health(
    project_key: str,
    period_days: int = Query(30, ge=7, le=90),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Возвращает Project Health Score (0-100).
    
    Компоненты:
    - SLA Score (30%)
    - Stability Score (30%)
    - Workload Balance (30%)
    - Deadline Stability (10%)
    """
    from app.services.metrics.health_score import calculate_health_score
    from app.services.metrics.sla_score import calculate_sla_score
    from app.services.metrics.workload_index import calculate_workload_index
    from app.db.models import JiraIssue
    
    # Получаем компоненты
    sla = calculate_sla_score(db, project_key=project_key, period_days=period_days)
    health = calculate_health_score(db, project_key=project_key)
    
    # Получаем средний WI для оценки Workload Balance
    assignees = db.query(JiraIssue.assignee_account_id).filter(
        JiraIssue.project_key == project_key,
        JiraIssue.assignee_account_id.isnot(None)
    ).distinct().all()
    
    wi_values = []
    for (assignee_id,) in assignees:
        wi = calculate_workload_index(db, assignee_id, project_key, weeks=2)
        if wi:
            wi_values.append(wi)
    
    workload_balance = 100
    if wi_values and len(wi_values) > 1:
        # Чем меньше разброс, тем лучше
        max_wi = max(wi_values)
        min_wi = min(wi_values)
        if max_wi > 0:
            workload_balance = max(0, 100 - ((max_wi - min_wi) / max_wi * 100))
        workload_balance = round(workload_balance, 1)
    
    return {
        "success": True,
        "data": {
            "health_score": health['health_score'],
            "status": health['status'],
            "status_text": health['status_text'],
            "components": {
                "sla_score": sla['sla_score'],
                "stability_score": health['components']['stability_score'],
                "workload_balance": workload_balance,
                "deadline_stability": health['components']['deadline_stability']
            }
        },
        "project_key": project_key
    }

@router.post("/health/{project_key}/calculate")
def calculate_project_health(
    project_key: str,
    period_days: int = Query(30, ge=7, le=90),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Рассчитывает и сохраняет Project Health Score.
    """
    from app.services.metrics.health_score import calculate_health_score, save_health_score
    
    health_data = calculate_health_score(db, project_key, period_days)
    saved = save_health_score(db, project_key, health_data, period_days)
    
    if not saved:
        raise HTTPException(
            status_code=404, 
            detail=f"Project '{project_key}' not found in core.projects"
        )
    
    return {
        "success": True,
        "data": health_data,
        "project_key": project_key
    }


@router.get("/health/{project_key}")
def get_project_health(
    project_key: str,
    period_days: int = Query(30, ge=7, le=90),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Возвращает последний рассчитанный Health Score для проекта.
    Если нет сохранённых данных — рассчитывает «на лету».
    """
    from app.services.metrics.health_score import calculate_health_score
    from app.db.models.core import Project
    from app.db.timescale import timescale_engine
    from app.db.models.metrics import ProjectHealth
    from sqlalchemy.orm import Session as TimescaleSession
    
    project = db.query(Project).filter(Project.key == project_key).first()
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_key}' not found")
    
    period_end = datetime.utcnow()
    period_start = period_end - timedelta(days=period_days)
    
    # Пробуем получить сохранённые данные
    with TimescaleSession(timescale_engine) as ts_db:
        saved = ts_db.query(ProjectHealth).filter(
            ProjectHealth.project_id == project.id,
            ProjectHealth.period_start >= period_start,
            ProjectHealth.period_end <= period_end
        ).order_by(ProjectHealth.calculated_at.desc()).first()
        
        if saved:
            # Возвращаем полные данные с компонентами
            components = calculate_health_score(db, project_key, period_days)['components']
            return {
                "success": True,
                "data": {
                    "health_score": saved.health_score,
                    "status": saved.status,
                    "status_text": {
                        'green': 'Здоров',
                        'yellow': 'Риск',
                        'red': 'Критично'
                    }.get(saved.status, 'Unknown'),
                    "components": components,
                    "calculated_at": saved.calculated_at.isoformat() if saved.calculated_at else None
                },
                "project_key": project_key,
                "cached": True
            }
    
    # Если нет сохранённых — считаем на лету (но не сохраняем)
    health_data = calculate_health_score(db, project_key, period_days)
    return {
        "success": True,
        "data": health_data,
        "project_key": project_key,
        "cached": False
    }

# В app/endpoints/metrics_endpoints.py

@router.post("/health/{project_key}/calculate-async")
def calculate_project_health_async(
    project_key: str,
    period_days: int = Query(30, ge=7, le=90),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Запускает асинхронный расчёт Health Score через очередь.
    Возвращает job_id для отслеживания.
    """
    from app.workers.queues import calculate_metrics_queue
    from app.workers.tasks import calculate_project_health_task
    
    try:
        job = calculate_metrics_queue.enqueue(
            calculate_project_health_task,
            args=(current_user.id, project_key, period_days),
            job_timeout="120s",
            result_ttl=3600,
            failure_ttl=3600
        )
        
        return {
            "success": True,
            "message": f"Health Score calculation for {project_key} queued",
            "data": {
                "job_id": job.id,
                "status": "queued",
                "project_key": project_key,
                "period_days": period_days
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to queue calculation: {str(e)}"
        )