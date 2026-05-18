# app/db/models/core.py

"""Схема core — основные сущности системы (проекты, связи пользователей)"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, Text, Boolean
from sqlalchemy.orm import relationship
from app.db.base import Base


class Project(Base):
    """Проект — основная сущность системы"""
    __tablename__ = "projects"
    __table_args__ = {"schema": "core"}
    
    id = Column(Integer, primary_key=True)
    key = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    owner_id = Column(Integer, ForeignKey("identity.users.id", ondelete="SET NULL"), nullable=True)
    lead_account_id = Column(String(255), nullable=True, index=True)
    
    jira_project_key = Column(String(50), nullable=True, index=True)
    confluence_space_key = Column(String(255), nullable=True)
    
    github_repo = Column(String(255), nullable=True, index=True)
    github_instance_id = Column(String(255), nullable=True)
    
    url = Column(String(500), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    category = Column(String(100), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships — без backref, используем отдельный класс
    user_projects = relationship("UserProject", back_populates="project", cascade="all, delete-orphan")


class UserProject(Base):
    """Связь пользователей и проектов"""
    __tablename__ = "user_projects"
    __table_args__ = (
        UniqueConstraint("user_id", "project_id", name="uq_user_project"),
        {"schema": "core"}
    )
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("identity.users.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("core.projects.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(50), default="viewer")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    project = relationship("Project", back_populates="user_projects")
    # Связь с User пока убираем — будем использовать отдельные запросы