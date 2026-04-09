# tests/conftest.py - исправленный

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.db.models import User, IntegrationToken, Session as SessionModel
from datetime import datetime, timedelta
import secrets


# SQLite настройка
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db?check_same_thread=False"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# Удаляем схемы у всех таблиц
for table in Base.metadata.tables.values():
    table.schema = None
    if '.' in table.name:
        table.name = table.name.split('.')[-1]

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    """Создает таблицы в тестовой БД"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(setup_db):
    """Создает сессию БД для теста"""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def test_user(db_session):
    """Создает тестового пользователя"""
    user = User(
        email="test@example.com",
        display_name="Test User",
        avatar_url="https://example.com/avatar.jpg",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_session(db_session, test_user):
    """Создает тестовую сессию"""
    session_token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(days=7)
    
    session = SessionModel(
        user_id=test_user.id,
        session_token=session_token,
        expires_at=expires_at,
        client_type="web"
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    
    return session


@pytest.fixture
def test_token(db_session, test_user):
    """Создает тестовый токен"""
    token = IntegrationToken(
        user_id=test_user.id,
        provider="jira",
        provider_user_id="test_account_123",
        instance_id="test-cloud-id-123",
        instance_name="testsite",
        instance_url="https://testsite.atlassian.net",
        access_token="test_access_token",
        refresh_token="test_refresh_token",
        expires_at=datetime.utcnow() + timedelta(hours=1),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db_session.add(token)
    db_session.commit()
    db_session.refresh(token)
    return token


@pytest.fixture
def client():
    """HTTP клиент без авторизации"""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def auth_client(test_session):
    """HTTP клиент с авторизацией"""
    transport = ASGITransport(app=app)
    return AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={"session_token": test_session.session_token}
    )