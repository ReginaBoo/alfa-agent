# app/db/models/normalized.py
"""Схема normalized — нормализованные данные из внешних систем"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Float, Boolean, Index, ForeignKey
from app.db.base import Base

from sqlalchemy.orm import relationship


class JiraIssue(Base):
    __tablename__ = "jira_issues"
    __table_args__ = (
        {"schema": "normalized"}
    )

    id = Column(Integer, primary_key=True)
    project_integration_id = Column(Integer, nullable=True, index=True)
    issue_key = Column(String(255), unique=True, nullable=False, index=True)
    project_key = Column(String(255), nullable=False,
                         index=True)  # ← добавил поле
    summary = Column(Text, nullable=False)
    status = Column(String(100), nullable=False,
                    index=True)  # ← добавил индекс
    status_category = Column(String(50), nullable=True)
    assignee_account_id = Column(
        String(255), nullable=True, index=True)  # ← добавил индекс
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
    updated_at = Column(DateTime, nullable=False,
                        index=True)  # ← добавил индекс
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

    id = Column(String(50), primary_key=True)  # page_id из Confluence
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
    # ДОБАВЛЕНО: ForeignKey для связи с ConfluencePage
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

    # Связь со страницей (указываем foreign_keys явно)
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
    # ДОБАВЛЕНО: ForeignKey для связи с ConfluencePage
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

    # Связь со страницей
    page = relationship(
        "ConfluencePage",
        back_populates="comments",
        foreign_keys=[page_id]
    )
