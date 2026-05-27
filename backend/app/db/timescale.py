# app/db/timescale.py

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# Engine для TimescaleDB
timescale_engine = create_engine(
    settings.TIMESCALE_URL,
    pool_pre_ping=True,
    echo=False
)

# Сессия для TimescaleDB
TimescaleSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=timescale_engine
)

# Базовый класс для моделей TimescaleDB
TimescaleBase = declarative_base()


def get_timescale_db():
    """Dependency для получения сессии TimescaleDB"""
    db = TimescaleSessionLocal()
    try:
        yield db
    finally:
        db.close()