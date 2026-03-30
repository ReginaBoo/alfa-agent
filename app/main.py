import logging
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.endpoints import auth_endpoints, jira_endpoints
from app.db.base import Base
from app.db.session import engine

# Настройка логгирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Alpha Agent Backend")


# --- Подключение роутеров ---
app.include_router(auth_endpoints.router, prefix="/auth", tags=["Auth"])
app.include_router(jira_endpoints.router, prefix="/jira", tags=["Jira"])


# --- Startup / Shutdown ---
# --- Startup / Shutdown ---
@app.on_event("startup")
def on_startup():
    logger.info("Starting Alpha Agent Backend...")
    
    # Проверяем подключение к БД
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            logger.info("Database connection successful")
    except SQLAlchemyError as e:
        logger.error(f"Database connection failed: {e}")
        # В продакшене можно выбросить исключение
        # raise e
    
    logger.info("Alpha Agent Backend startup complete")


@app.on_event("shutdown")
def on_shutdown():
    logger.info("Shutting down Alpha Agent Backend...")
    
    # Закрываем пул соединений
    engine.dispose()
    logger.info("Database connections closed")


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