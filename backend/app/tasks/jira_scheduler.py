import asyncio
import logging
from datetime import datetime

from app.core.config import settings
from app.db.session import SessionLocal
from app.db.models import IntegrationToken
from app.db.models.identity import User

from app.workers.queues import sync_jira_queue
from app.workers.tasks import sync_jira_task

logger = logging.getLogger(__name__)

# Настройки расписания
CYCLE_INTERVAL = 1800  # 30 минут между циклами
FULL_SYNC_INTERVAL = 48  # раз в 48 циклов (раз в 24 часа при 30-минутном интервале)


async def schedule_jira_sync():
    logger.info("Jira scheduler started")
    
    full_sync_counter = 0
    
    while True:
        logger.info("========== JIRA SYNC CYCLE START ==========")
        db = SessionLocal()
        
        try:
            excluded_emails = set(
                email.strip()
                for email in settings.JIRA_SYNC_EXCLUDED_USERS.split(",")
                if email.strip()
            )
            
            tokens = (
                db.query(IntegrationToken)
                .join(User)
                .filter(IntegrationToken.provider == "jira")
                .all()
            )
            
            logger.info(f"Found {len(tokens)} Jira integration tokens")
            
            # Определяем тип синхронизации
            full_sync = (full_sync_counter % FULL_SYNC_INTERVAL == 0)
            sync_type = "FULL" if full_sync else "INCREMENTAL"
            logger.info(f"Sync type: {sync_type} (counter: {full_sync_counter})")
            
            queued_jobs = 0
            
            for token in tokens:
                user = token.user
                
                if user.email in excluded_emails:
                    logger.info(f"Skipping excluded user: {user.email}")
                    continue
                
                try:
                    job = sync_jira_queue.enqueue(
                        sync_jira_task,
                        user_id=user.id,
                        instance_name=token.instance_name,
                        full_sync=full_sync,  # ← передаем параметр
                        job_timeout="1h" if full_sync else "10m"
                    )
                    
                    queued_jobs += 1
                    logger.info(f"Successfully queued job: job_id={job.id}, full_sync={full_sync}")
                    
                except Exception:
                    logger.exception(f"Failed to enqueue sync task for user_id={user.id}")
            
            logger.info(f"Cycle finished. Queued jobs: {queued_jobs}, type: {sync_type}")
            
            full_sync_counter += 1
            
        except Exception:
            logger.exception("Jira scheduler failed")
        finally:
            db.close()
        
        logger.info("========== JIRA SYNC CYCLE END ==========")
        
        await asyncio.sleep(CYCLE_INTERVAL)