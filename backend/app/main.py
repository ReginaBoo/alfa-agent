import logging
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.endpoints import auth_endpoints, jira_endpoints
from app.db.base import Base
from app.db.session import engine
from app.endpoints import health
from app.endpoints import worker_test
from app.endpoints import dashboard_endpoints
from app.endpoints import confluence_endpoints
from app.endpoints import job_status
from app.endpoints import metrics_endpoints
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.workers.queues import sync_jira_queue
from app.workers.tasks import sync_jira_task

# Настройка логгирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Alpha Agent Backend")
scheduler = BackgroundScheduler()

# --- Подключение роутеров ---
app.include_router(auth_endpoints.router, prefix="/auth", tags=["Auth"])
app.include_router(jira_endpoints.router, prefix="/jira", tags=["Jira"])
app.include_router(worker_test.router, prefix="/worker", tags=["Worker"])
app.include_router(dashboard_endpoints.router, prefix="/dashboard", tags=["Dashboard"])
app.include_router(confluence_endpoints.router, prefix="/confluence", tags=["Confluence"])
app.include_router(job_status.router, tags=["Job Status"])
app.include_router(metrics_endpoints.router, prefix="/metrics", tags=["Metrics"])

# --- Модифицируем on_startup ---
@app.on_event("startup")
def on_startup():
    logger.info("Starting Alpha Agent Backend...")

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            logger.info("Database connection successful")
    except SQLAlchemyError as e:
        logger.error(f"Database connection failed: {e}")

    scheduler.add_job(
        func=scheduled_jira_sync,
        trigger=IntervalTrigger(hours=1),
        id="scheduled_jira_sync",
        replace_existing=True
    )

    scheduler.start()
    logger.info("APScheduler started")


@app.on_event("shutdown")
def on_shutdown():
    logger.info("Shutting down Alpha Agent Backend...")

    scheduler.shutdown(wait=False)
    engine.dispose()


@app.get("/health")
def health():
    """Health check endpoint for monitoring"""
    db_status = "unknown"
    error = None
    
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            db_status = "connected"
    except SQLAlchemyError as e:
        db_status = "disconnected"
        error = str(e)
    
    return {
        "status": "ok" if db_status == "connected" else "degraded",
        "database": db_status,
        "error": error
    }

# --- Функция для запуска синхронизации по расписанию ---
def scheduled_jira_sync():
    """
    Запускает фоновую синхронизацию всех проектов для всех пользователей.
    Вызывается APScheduler раз в час.
    """
    from app.db.session import SessionLocal
    from app.db.models import IntegrationToken
    
    logger.info("Scheduled Jira sync started")
    
    db = SessionLocal()
    try:
        # Получаем всех пользователей, у которых есть токены
        tokens = db.query(IntegrationToken).filter(
            IntegrationToken.provider == "jira"
        ).distinct(IntegrationToken.user_id, IntegrationToken.instance_name).all()
        
        for token in tokens:
            logger.info(f"Queuing sync for user {token.user_id}, instance {token.instance_name}")
            
            # Ставим задачу в очередь БЕЗ project_key = все проекты
            sync_jira_queue.enqueue(
                sync_jira_task,
                args=(token.user_id, token.instance_name, None),  # None = все проекты
                job_timeout="900s",  # 15 минут на все проекты
                result_ttl=3600,
                failure_ttl=3600
            )
        
        logger.info(f"Scheduled sync queued for {len(tokens)} users")
        
    except Exception as e:
        logger.error(f"Scheduled sync failed: {e}")
    finally:
        db.close()
