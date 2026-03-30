# backend/app/db/session.py
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import Session as SQLAlchemySession
from app.core.config import settings

logger = logging.getLogger(__name__)

DATABASE_URL = (
    f"postgresql://{settings.POSTGRES_USER}:"
    f"{settings.POSTGRES_PASSWORD}@"
    f"{settings.POSTGRES_HOST}:"
    f"{settings.POSTGRES_PORT}/"
    f"{settings.POSTGRES_DB}"
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # проверяет соединение перед использованием
    pool_size=10,        # размер пула соединений
    max_overflow=20      # максимальное дополнительных соединений
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> SQLAlchemySession:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Функция для проверки подключения при старте приложения
def test_db_connection():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            logger.info("Database connection successful")
            return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False