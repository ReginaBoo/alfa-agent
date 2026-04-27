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