# app/endpoints/worker_test.py
from fastapi import APIRouter, HTTPException
from app.workers.queues import sync_jira_queue
from app.workers.tasks import ping_task

router = APIRouter()


@router.post("/test")
def enqueue_test_task(message: str = "Hello from RQ!"):
    """Отправляет тестовую задачу в очередь sync_jira"""
    try:
        job = sync_jira_queue.enqueue(
            ping_task,
            message,
            job_timeout="30s",
            failure_ttl=3600,
            result_ttl=3600
        )
        return {
            "success": True,
            "data": {
                "job_id": job.id,
                "status": job.get_status(),
                "queue": job.origin
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to enqueue job: {str(e)}")


@router.get("/job/{job_id}")
def get_job_status(job_id: str):
    """Проверяет статус задачи по ID"""
    from rq.job import Job
    from app.workers.queues import redis_conn
    
    try:
        job = Job.fetch(job_id, connection=redis_conn)
        return {
            "success": True,
            "data": {
                "job_id": job.id,
                "status": job.get_status(),
                "result": job.result if job.is_finished else None,
                "error": str(job.exc_info) if job.is_failed else None
            }
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Job not found: {str(e)}")