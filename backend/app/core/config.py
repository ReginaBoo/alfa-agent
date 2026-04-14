# /backend/app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"  # Игнорируем лишние поля
    )

    # App
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # Postgres (основная БД)
    POSTGRES_DB: str = "app_db"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_HOST: str = "db"
    POSTGRES_PORT: int = 5432  # Внутренний порт контейнера!

    # TimescaleDB (метрики)
    TIMESCALE_DB: str = "metrics_db"
    TIMESCALE_USER: str = "postgres"
    TIMESCALE_PASSWORD: str = "postgres"
    TIMESCALE_HOST: str = "timescaledb"
    TIMESCALE_PORT: int = 5432  # Внутренний порт контейнера!

    # Atlassian
    ATLASSIAN_CLIENT_ID: str
    ATLASSIAN_CLIENT_SECRET: str
    ATLASSIAN_REDIRECT_URI: str = "http://localhost:8000/auth/callback"
    SCOPES: str = "read:jira-user read:jira-work read:confluence-space:confluence read:confluence-content:confluence read:confluence-props:confluence offline_access"

    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    
    REDIS_URL: str = "redis://redis:6379/0" 

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def TIMESCALE_URL(self) -> str:
        return f"postgresql://{self.TIMESCALE_USER}:{self.TIMESCALE_PASSWORD}@{self.TIMESCALE_HOST}:{self.TIMESCALE_PORT}/{self.TIMESCALE_DB}"

settings = Settings()