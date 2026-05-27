# backend/app/db/models.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, Float, Text, JSON
from sqlalchemy.orm import relationship 
from datetime import datetime
from app.db.base import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    atlassian_account_id = Column(String, unique=True, index=True)
    email = Column(String)
    display_name = Column(String)
    avatar_url = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships - добавляем для удобства
    tokens = relationship("AtlassianToken", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")


class AtlassianToken(Base):
    __tablename__ = "atlassian_tokens"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    atlassian_account_id = Column(String, index=True, nullable=False)
    cloud_id = Column(String, index=True, nullable=False)
    site_url = Column(String, nullable=True)
    site_name = Column(String, nullable=True)
    access_token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=False)
    expires_at = Column(DateTime, index=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('user_id', 'cloud_id', name='uq_user_cloud'),
    )
    
    user = relationship("User", back_populates="tokens")


class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_token = Column(String, unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="sessions")


# Добавь это в конец файла app/db/models.py


class RawEvent(Base):
    __tablename__ = "raw_events"
    
    id = Column(Integer, primary_key=True)
    source = Column(String(50), nullable=False, index=True)  # jira, confluence, github
    event_type = Column(String(100), nullable=False, index=True)  # issue, project, page
    external_id = Column(String(255), nullable=False, index=True)
    project_integration_id = Column(Integer, nullable=True)
    payload = Column(JSON, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)


class JiraIssue(Base):
    __tablename__ = "jira_issues"
    
    id = Column(Integer, primary_key=True)
    issue_key = Column(String(255), unique=True, nullable=False, index=True)
    project_key = Column(String(255), nullable=False, index=True)
    summary = Column(Text, nullable=False)
    status = Column(String(100), nullable=False, index=True)
    assignee_account_id = Column(String(255), nullable=True, index=True)
    assignee_name = Column(String(255), nullable=True)
    reporter_account_id = Column(String(255), nullable=True)
    priority = Column(String(50), nullable=True)
    issue_type = Column(String(100), nullable=False)
    story_points = Column(Float, nullable=True)
    due_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False, index=True)
    last_synced_at = Column(DateTime, default=datetime.utcnow)