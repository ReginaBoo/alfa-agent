# app/db/models/normalized.py
"""Схема normalized — нормализованные данные из внешних систем"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Float, Boolean, Index, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import ARRAY
from app.db.base import Base
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import relationship


class JiraIssue(Base):
    __tablename__ = "jira_issues"
    __table_args__ = (
        {"schema": "normalized"}
    )

    id = Column(Integer, primary_key=True)
    project_integration_id = Column(Integer, nullable=True, index=True)
    issue_key = Column(String(255), unique=True, nullable=False, index=True)
    project_key = Column(String(255), nullable=False, index=True)
    summary = Column(Text, nullable=False)
    status = Column(String(100), nullable=False, index=True)
    status_category = Column(String(50), nullable=True)
    assignee_account_id = Column(String(255), nullable=True, index=True)
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
    closed_at = Column(DateTime, nullable=True, index=True)  # ← НОВОЕ ПОЛЕ
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False, index=True)
    last_synced_at = Column(DateTime, default=datetime.utcnow)
    is_deleted = Column(Boolean, default=False)
    snapshot_version = Column(Integer, default=1)


class IssueChangelog(Base):
    """История изменений задач Jira"""
    __tablename__ = "issue_changelog"
    __table_args__ = (
        Index("idx_changelog_issue_key", "issue_key"),
        Index("idx_changelog_field", "field_name"),
        Index("idx_changelog_changed_at", "changed_at"),
        {"schema": "normalized"}
    )

    id = Column(Integer, primary_key=True)
    issue_key = Column(String(255), nullable=False, index=True)
    field_name = Column(String(100), nullable=False)
    from_value = Column(String(255), nullable=True)
    to_value = Column(String(255), nullable=True)
    changed_at = Column(DateTime, nullable=False)
    author_account_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ConfluencePage(Base):
    """Страница Confluence"""
    __tablename__ = "confluence_pages"
    __table_args__ = (
        Index("idx_confluence_pages_space", "space_id"),
        Index("idx_confluence_pages_author", "author_id"),
        Index("idx_confluence_pages_updated", "updated_at"),
        {"schema": "normalized"}
    )

    id = Column(String(50), primary_key=True)
    space_id = Column(String(50), nullable=False, index=True)
    space_key = Column(String(255), nullable=True)
    title = Column(Text, nullable=False)
    author_id = Column(String(255), nullable=True, index=True)
    author_name = Column(String(255), nullable=True)
    version = Column(Integer, default=1)
    status = Column(String(50), default="current")
    parent_id = Column(String(50), nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False, index=True)
    content = Column(Text, nullable=True)
    content_format = Column(String(50), default="storage")
    last_synced_at = Column(DateTime, default=datetime.utcnow)
    is_deleted = Column(Boolean, default=False)

    # Связи с версиями и комментариями (обратные)
    versions = relationship(
        "ConfluencePageVersion",
        back_populates="page",
        cascade="all, delete-orphan",
        foreign_keys="ConfluencePageVersion.page_id"
    )
    comments = relationship(
        "ConfluenceComment",
        back_populates="page",
        cascade="all, delete-orphan",
        foreign_keys="ConfluenceComment.page_id"
    )


class ConfluencePageVersion(Base):
    """Версия страницы Confluence"""
    __tablename__ = "confluence_page_versions"
    __table_args__ = (
        Index("idx_page_versions_page", "page_id", "version_number"),
        {"schema": "normalized"}
    )

    id = Column(Integer, primary_key=True)
    page_id = Column(
        String(50),
        ForeignKey("normalized.confluence_pages.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    version_number = Column(Integer, nullable=False)
    message = Column(Text, nullable=True)
    author_id = Column(String(255), nullable=True, index=True)
    author_name = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False)
    minor_edit = Column(Boolean, default=False)

    page = relationship(
        "ConfluencePage",
        back_populates="versions",
        foreign_keys=[page_id]
    )


class ConfluenceComment(Base):
    """Комментарий к странице Confluence"""
    __tablename__ = "confluence_comments"
    __table_args__ = (
        Index("idx_comments_page", "page_id"),
        Index("idx_comments_author", "author_id"),
        Index("idx_comments_resolved", "is_resolved"),
        {"schema": "normalized"}
    )

    id = Column(String(50), primary_key=True)
    page_id = Column(
        String(50),
        ForeignKey("normalized.confluence_pages.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    author_id = Column(String(255), nullable=True, index=True)
    author_name = Column(String(255), nullable=True)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=True)
    is_resolved = Column(Boolean, default=False, index=True)
    parent_id = Column(String(50), nullable=True)
    position = Column(String(20), nullable=True)

    page = relationship(
        "ConfluencePage",
        back_populates="comments",
        foreign_keys=[page_id]
    )


class GithubIssue(Base):
    """Нормализованные данные из GitHub Issues"""
    __tablename__ = "github_issues"
    __table_args__ = (
        Index("idx_github_issues_repo", "repo_full_name"),
        Index("idx_github_issues_state", "state"),
        Index("idx_github_issues_assignee", "assignee_login"),
        Index("idx_github_issues_updated", "updated_at"),
        {"schema": "normalized"}
    )
    
    id = Column(Integer, primary_key=True)
    project_integration_id = Column(Integer, nullable=True, index=True)
    
    issue_id = Column(Integer, nullable=False, index=True)
    issue_number = Column(Integer, nullable=False)
    repo_full_name = Column(String(255), nullable=False, index=True)
    repo_id = Column(Integer, nullable=True)
    
    title = Column(Text, nullable=False)
    body = Column(Text, nullable=True)
    state = Column(String(50), nullable=False, index=True)
    locked = Column(Boolean, default=False)
    
    author_login = Column(String(255), nullable=True, index=True)
    author_id = Column(Integer, nullable=True)
    assignee_login = Column(String(255), nullable=True, index=True)
    assignee_id = Column(Integer, nullable=True)
    
    labels = Column(JSON, nullable=True)
    milestone_id = Column(Integer, nullable=True)
    milestone_title = Column(String(255), nullable=True)
    
    project_id = Column(Integer, nullable=True)
    
    comments_count = Column(Integer, default=0)
    
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False, index=True)
    closed_at = Column(DateTime, nullable=True)
    
    last_synced_at = Column(DateTime, default=datetime.utcnow)
    is_deleted = Column(Boolean, default=False)
    snapshot_version = Column(Integer, default=1)
    
    html_url = Column(String(500), nullable=True)


class GithubIssueEvent(Base):
    """История событий GitHub Issue"""
    __tablename__ = "github_issue_events"
    __table_args__ = (
        Index("idx_github_events_issue", "issue_id"),
        Index("idx_github_events_event_type", "event_type"),
        Index("idx_github_events_created_at", "created_at"),
        {"schema": "normalized"}
    )
    
    id = Column(Integer, primary_key=True)
    issue_id = Column(Integer, nullable=False, index=True)
    repo_full_name = Column(String(255), nullable=False)
    
    event_type = Column(String(100), nullable=False)
    external_event_id = Column(Integer, nullable=False, index=True)
    
    actor_login = Column(String(255), nullable=True)
    actor_id = Column(Integer, nullable=True)
    
    detail_login = Column(String(255), nullable=True)
    detail_id = Column(Integer, nullable=True)
    
    commit_id = Column(String(40), nullable=True)
    commit_url = Column(String(500), nullable=True)
    state = Column(String(50), nullable=True)
    
    created_at = Column(DateTime, nullable=False, index=True)
    synced_at = Column(DateTime, default=datetime.utcnow)



class ProjectStatusMapping(Base):
    """Маппинг статусов Jira проекта с их ролями для метрик"""
    __tablename__ = "project_status_mappings"
    __table_args__ = (
        UniqueConstraint('project_key', 'status_name', name='uq_project_status'),
        Index("idx_project_status_mappings_project", "project_key"),
        Index("idx_project_status_mappings_status", "status_name"),
        {"schema": "normalized"}  # ← ВАЖНО: добавляем в схему normalized
    )

    id = Column(Integer, primary_key=True)
    project_key = Column(String(255), nullable=False, index=True)  # Jira project key
    
    # Статус из Jira (например, "Code Review", "In Progress", "Готово")
    status_name = Column(String(100), nullable=False)
    
    # Роли статуса для метрик
    is_open = Column(Boolean, default=True)           # Учитывается в Workload Index?
    is_in_progress = Column(Boolean, default=False)   # Штраф за многозадачность?
    is_closed = Column(Boolean, default=False)        # Считается завершённой?
    
    # Категория статуса из Jira (todo, in-progress, done)
    jira_category = Column(String(50), nullable=True)
    
    # Кэш: когда последний раз обновляли из Jira
    last_synced_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Кто обновил (account_id пользователя, который синхронизировал)
    synced_by_account_id = Column(String(255), nullable=True)
    
    def __repr__(self):
        return f"<ProjectStatusMapping {self.project_key}:{self.status_name} (open={self.is_open}, progress={self.is_in_progress}, closed={self.is_closed})>"