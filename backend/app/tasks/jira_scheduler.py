# app/tasks/jira_scheduler.py
import asyncio
import logging

from app.core.config import settings
from app.db.session import SessionLocal
from app.db.models import IntegrationToken
from app.db.models.identity import User

from app.workers.queues import sync_jira_queue
from app.workers.tasks import sync_jira_task

logger = logging.getLogger(__name__)


async def schedule_jira_sync():

    logger.info("Jira scheduler started")

    while True:

        logger.info("========== JIRA SYNC CYCLE START ==========")

        db = SessionLocal()

        try:

            excluded_emails = set(
                email.strip()
                for email in settings.JIRA_SYNC_EXCLUDED_USERS.split(",")
                if email.strip()
            )

            logger.info(
                f"Excluded users: {list(excluded_emails) if excluded_emails else 'none'}"
            )

            tokens = (
                db.query(IntegrationToken)
                .join(User)
                .filter(
                    IntegrationToken.provider == "jira"
                )
                .all()
            )

            logger.info(f"Found {len(tokens)} Jira integration tokens")

            if not tokens:
                logger.warning("No Jira tokens found")

            queued_jobs = 0

            for token in tokens:

                user = token.user

                logger.info(
                    f"Processing token: "
                    f"user_id={user.id}, "
                    f"email={user.email}, "
                    f"instance={token.instance_name}"
                )

                if user.email in excluded_emails:
                    logger.info(
                        f"Skipping excluded user: {user.email}"
                    )
                    continue

                try:

                    logger.info(
                        f"Queueing Jira sync: "
                        f"user_id={user.id}, "
                        f"instance={token.instance_name}"
                    )

                    job = sync_jira_queue.enqueue(
                        sync_jira_task,
                        user_id=user.id,
                        instance_name=token.instance_name,
                        job_timeout="1h"
                    )

                    queued_jobs += 1

                    logger.info(
                        f"Successfully queued job: "
                        f"job_id={job.id}, "
                        f"user_id={user.id}, "
                        f"instance={token.instance_name}"
                    )

                except Exception:
                    logger.exception(
                        f"Failed to enqueue sync task "
                        f"for user_id={user.id}, "
                        f"instance={token.instance_name}"
                    )

            logger.info(
                f"Cycle finished. "
                f"Queued jobs: {queued_jobs}"
            )

        except Exception:
            logger.exception("Jira scheduler failed")

        finally:
            db.close()

        logger.info(
            "========== JIRA SYNC CYCLE END =========="
        )

        await asyncio.sleep(300)