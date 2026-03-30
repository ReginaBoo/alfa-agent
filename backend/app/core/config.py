# /backend/app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    # App
    APP_HOST: str
    APP_PORT: int

    # Postgres
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int

    # Atlassian
    ATLASSIAN_CLIENT_ID: str
    ATLASSIAN_CLIENT_SECRET: str
    ATLASSIAN_REDIRECT_URI: str
    SCOPES: str = "read:jira-user read:jira-work offline_access"

    # Security
    SECRET_KEY: str

settings = Settings()