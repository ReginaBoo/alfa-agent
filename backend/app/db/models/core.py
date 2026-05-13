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
    key = Column(String(50), unique=True, nullable=False, index=True)  # SCRUM, FASAGM
    name = Column(String(255), nullable=False)  # Полное название проекта
    description = Column(Text, nullable=True)
    
    # Внешние связи
    owner_id = Column(Integer, ForeignKey("identity.users.id", ondelete="SET NULL"), nullable=True)
    lead_account_id = Column(String(255), nullable=True, index=True)  # Руководитель проекта (accountId из Jira)
    
    # Внешние идентификаторы
    jira_project_key = Column(String(50), nullable=True, index=True)  # Связь с Jira
    confluence_space_key = Column(String(255), nullable=True)  # Связь с Confluence
    
    github_repo = Column(String(255), nullable=True, index=True)  # owner/repo
    github_instance_id = Column(String(255), nullable=True)      # GitHub username/organization
    
    # Метаданные
    url = Column(String(500), nullable=True)  # URL проекта в Jira
    avatar_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)  # Архивные проекты
    category = Column(String(100), nullable=True)  # Для группировки (backend, frontend, devops)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    owner = relationship("User", foreign_keys=[owner_id])
    users = relationship("UserProject", back_populates="project")


class UserProject(Base):
    """Связь пользователей и проектов (многие-ко-многим)"""
    __tablename__ = "user_projects"
    __table_args__ = (
        UniqueConstraint("user_id", "project_id", name="uq_user_project"),
        {"schema": "core"}
    )
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("identity.users.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("core.projects.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(50), default="viewer")  # owner, manager, viewer, developer, analyst
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    project = relationship("Project", back_populates="users")