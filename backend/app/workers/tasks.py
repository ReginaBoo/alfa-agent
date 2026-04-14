# app/workers/tasks.py
import logging
import time

logger = logging.getLogger(__name__)


def ping_task(message: str) -> dict:
    """Простая тестовая задача для проверки работы очередей"""
    
    return {
        "status": "completed",
        "message": message,
        "timestamp": time.time()
    }