# app/db/models/normalized.py
"""Схема normalized — нормализованные данные из внешних систем"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Float, Boolean, Index
from app.db.base import Base


class JiraIssue(Base):
    __tablename__ = "jira_issues"
    __table_args__ = (
        {"schema": "normalized"}
    )
    
    id = Column(Integer, primary_key=True)
    project_integration_id = Column(Integer, nullable=True, index=True)
    issue_key = Column(String(255), unique=True, nullable=False, index=True)
    project_key = Column(String(255), nullable=False, index=True)  # ← добавил поле
    summary = Column(Text, nullable=False)
    status = Column(String(100), nullable=False, index=True)  # ← добавил индекс
    status_category = Column(String(50), nullable=True)
    assignee_account_id = Column(String(255), nullable=True, index=True)  # ← добавил индекс
    assignee_name = Column(String(255), nullable=True)
    assignee_user_id = Column(Integer, nullable=True)
    reporter_account_id = Column(String(255), nullable=True)
    priority = Column(String(50), nullable=True)
    issue_type = Column(String(100), nullable=False)
    story_points = Column(Float, nullable=True)
    original_estimate = Column(Float, nullable=True)
    time_spent = Column(Float, nullable=True)
    remaining_estimate = Column(Float, nullable=True)
    due_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False, index=True)  # ← добавил индекс
    last_synced_at = Column(DateTime, default=datetime.utcnow)
    is_deleted = Column(Boolean, default=False)
    snapshot_version = Column(Integer, default=1)