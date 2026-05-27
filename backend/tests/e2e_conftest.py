"""
Conftest для E2E тестов — общие fixtures и настройки.
"""

import pytest
import os
from typing import Generator
from sqlalchemy.orm import Session

from app.db.session import SessionLocal


@pytest.fixture(scope="session")
def test_env():
    """Загрузка тестовых переменных окружения"""
    return {
        "jira_instance": os.getenv("TEST_JIRA_INSTANCE", "testsite"),
        "github_instance": os.getenv("TEST_GITHUB_INSTANCE", "testuser"),
        "base_url": os.getenv("TEST_BASE_URL", "http://localhost:8000"),
        "cleanup_on_finish": os.getenv("E2E_CLEANUP", "true").lower() == "true"
    }


@pytest.fixture(scope="session")
def db_engine():
    """Engine для БД (shared для всех E2E тестов)"""
    from app.db.session import engine
    return engine


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """
    Функциональная сессия БД — откат после каждого теста.
    Использует SAVEPOINT для изоляции тестов.
    """
    from sqlalchemy import text
    
    db = SessionLocal()
    
    # Начинаем транзакцию
    db.begin()
    
    try:
        yield db
        # Откат если тест не завершён успешно
        db.rollback()
    finally:
        db.close()


@pytest.fixture(scope="function")
def clean_database(db_session: Session):
    """
    Fixture для очистки БД перед и после теста.
    Используется @pytest.mark.usefixtures("clean_database")
    """
    from app.db.models import RawEvent, IntegrationToken
    from app.db.models.normalized import (
        JiraIssue, IssueChangelog, ProjectStatusMapping,
        ConfluencePage, GithubIssue, GithubIssueEvent
    )
    from app.db.models.core import Project, UserProject
    from app.db.models.identity import User, Session, IntegrationToken as IdToken
    
    # Очистка перед тестом
    db_session.query(RawEvent).delete()
    db_session.query(IssueChangelog).delete()
    db_session.query(JiraIssue).delete()
    db_session.query(GithubIssue).delete()
    db_session.query(GithubIssueEvent).delete()
    db_session.query(ConfluencePage).delete()
    db_session.query(ProjectStatusMapping).delete()
    db_session.query(UserProject).delete()
    db_session.query(Project).delete()
    
    db_session.commit()
    
    yield db_session
    
    # Очистка после теста (опционально)
    if os.getenv("E2E_CLEANUP", "true").lower() == "true":
        db_session.query(RawEvent).delete()
        db_session.query(IssueChangelog).delete()
        db_session.query(JiraIssue).delete()
        db_session.query(ProjectStatusMapping).delete()
        db_session.commit()


@pytest.fixture(scope="session")
def skip_if_no_auth():
    """
    Fixture для пропуска тестов если нет авторизации.
    """
    import requests
    
    def _check(base_url: str) -> bool:
        """Проверяет, есть ли активная сессия"""
        response = requests.get(f"{base_url}/dashboard/digest")
        return response.status_code != 401
    
    return _check


# ================= MARKERS =================

def pytest_configure(config):
    """Регистрация кастомных маркеров"""
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow (can be skipped)"
    )
    config.addinivalue_line(
        "markers", "requires_auth: mark test as requiring authentication"
    )


def pytest_collection_modifyitems(config, items):
    """Фильтрация тестов по маркерам"""
    # Если передан флаг --skip-slow, пропускаем медленные тесты
    if config.getoption("--skip-slow"):
        skip_slow = pytest.mark.skip(reason="skipped because --skip-slow")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)


def pytest_addoption(parser):
    """Добавление опций командной строки"""
    parser.addoption(
        "--skip-slow",
        action="store_true",
        default=False,
        help="Skip slow tests"
    )
    parser.addoption(
        "--jira-instance",
        action="store",
        default="testsite",
        help="Jira instance name for tests"
    )
    parser.addoption(
        "--e2e-cleanup",
        action="store_true",
        default=True,
        help="Clean up test data after tests"
    )
