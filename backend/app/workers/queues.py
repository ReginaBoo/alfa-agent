# app/workers/queues.py

from redis import Redis
from rq import Queue
from app.core.config import settings

# Подключение к Redis
redis_conn = Redis.from_url(settings.REDIS_URL)

# Очереди
sync_jira_queue = Queue("sync_jira", connection=redis_conn, default_timeout=300)
sync_confluence_queue = Queue("sync_confluence", connection=redis_conn, default_timeout=300)
sync_github_queue = Queue("sync_github", connection=redis_conn, default_timeout=300)
calculate_metrics_queue = Queue("calculate_metrics", connection=redis_conn, default_timeout=300)

# Словарь для удобного доступа
QUEUES = {
    "sync_jira": sync_jira_queue,
    "sync_confluence": sync_confluence_queue,
    "sync_github": sync_github_queue,
    "calculate_metrics": calculate_metrics_queue,
}