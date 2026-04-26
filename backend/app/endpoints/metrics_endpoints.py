# app/endpoints/metrics_endpoints.py

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List

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