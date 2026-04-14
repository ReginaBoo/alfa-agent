# app/endpoints/health.py
from fastapi import APIRouter, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timezone

from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from app.db.session import engine
from app.db.timescale import timescale_engine
from app.core.config import settings

router = APIRouter()


def check_postgres() -> tuple[bool, str | None]:
    """Проверка основного PostgreSQL"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, None
    except SQLAlchemyError as e:
        return False, str(e)


def check_timescale() -> tuple[bool, str | None]:
    """Проверка TimescaleDB"""
    try:
        with timescale_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, None
    except SQLAlchemyError as e:
        return False, str(e)


def check_redis() -> tuple[bool, str | None]:
    """Проверка Redis — заглушка, пока не установлен пакет"""
    try:
        r = Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        r.ping()
        return True, None
    except (RedisConnectionError, Exception) as e:
        return False, str(e)
    return True, None  # временная заглушка


@router.get("/health", status_code=status.HTTP_200_OK)
def health_check(public: bool = True):
    """
    Health check endpoint.
    
    Если public=True — возвращает только статус (для балансировщиков).
    Если public=False — возвращает детальную информацию.
    """
    pg_ok, pg_err = check_postgres()
    ts_ok, ts_err = check_timescale()
    redis_ok, redis_err = check_redis()
    
    all_healthy = pg_ok and ts_ok and redis_ok
    
    timestamp = datetime.now(timezone.utc).isoformat()
    
    if public:
        return {
            "success": True,
            "data": {"status": "healthy" if all_healthy else "degraded"},
            "meta": {"timestamp": timestamp}
        }
    
    return {
        "success": all_healthy,
        "data": {
            "status": "healthy" if all_healthy else "degraded",
            "services": {
                "postgres": {"ok": pg_ok, "error": pg_err},
                "timescaledb": {"ok": ts_ok, "error": ts_err},
                "redis": {"ok": redis_ok, "error": redis_err}
            }
        },
        "meta": {"timestamp": timestamp}
    }