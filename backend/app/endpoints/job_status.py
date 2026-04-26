# app/endpoints/job_status.py

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session

from app.workers.queues import redis_conn

router = APIRouter()


@router.get("/job/{job_id}")
def get_job_status(job_id: str):
    """
    Проверяет статус задачи по job_id.
    """
    try:
        from rq.job import Job
        job = Job.fetch(job_id, connection=redis_conn)
        
        result = {
            "success": True,
            "data": {
                "job_id": job.id,
                "status": job.get_status(),
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "ended_at": job.ended_at.isoformat() if job.ended_at else None,
            }
        }
        
        if job.is_finished:
            result["data"]["result"] = job.result
        elif job.is_failed:
            result["data"]["error"] = str(job.exc_info)
        
        return result
        
    except ImportError:
        # Если rq не установлен
        return {
            "success": False,
            "error": "RQ not installed. Run: pip install rq redis"
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Job not found: {str(e)}")