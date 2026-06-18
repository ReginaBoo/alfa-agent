# /backend/app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    # App
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # Postgres (основная БД)
    POSTGRES_DB: str = "app_db"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_HOST: str = "db"
    POSTGRES_PORT: int = 5432

    # TimescaleDB (метрики)
    TIMESCALE_DB: str = "metrics_db"
    TIMESCALE_USER: str = "postgres"
    TIMESCALE_PASSWORD: str = "postgres"
    TIMESCALE_HOST: str = "timescaledb"
    TIMESCALE_PORT: int = 5432

    # Atlassian
    ATLASSIAN_CLIENT_ID: str
    ATLASSIAN_CLIENT_SECRET: str
    ATLASSIAN_REDIRECT_URI: str = "http://localhost:8000/auth/callback"
    # Добавлен write:jira-work для редактирования задач
    SCOPES: str = "read:jira-user read:jira-work write:jira-work read:confluence-user read:confluence-space.summary read:confluence-props read:confluence-content.summary search:confluence read:confluence-content.all read:space:confluence read:page:confluence offline_access read:comment:confluence"

    # GitHub
    GITHUB_CLIENT_ID: Optional[str] = None
    GITHUB_CLIENT_SECRET: Optional[str] = None
    GITHUB_REDIRECT_URI: str = "http://localhost:8000/github/callback"
    GITHUB_SCOPES: str = "repo user:email read:org"

    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    
    REDIS_URL: str = "redis://redis:6379/0"
    OPENROUTER_API_KEY: str
    OPENROUTER_MODEL: str = "openai/gpt-4o-mini"

    JIRA_SYNC_EXCLUDED_USERS: str = ""

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def TIMESCALE_URL(self) -> str:
        return f"postgresql://{self.TIMESCALE_USER}:{self.TIMESCALE_PASSWORD}@{self.TIMESCALE_HOST}:{self.TIMESCALE_PORT}/{self.TIMESCALE_DB}"

settings = Settings()