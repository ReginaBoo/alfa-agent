"""Схема identity — пользователи и доступ"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, JSON
from sqlalchemy.orm import relationship
from app.db.base import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "identity"}
    
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=False)
    avatar_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    tokens = relationship("IntegrationToken", back_populates="user", cascade="all, delete-orphan")


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = {"schema": "identity"}
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("identity.users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    client_type = Column(String(50), nullable=True)  # web, desktop
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="sessions")


class IntegrationToken(Base):
    __tablename__ = "integration_tokens"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", "instance_id", name="uq_user_provider_instance"),
        {"schema": "identity"}
    )
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("identity.users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String(50), nullable=False, index=True)  # jira, github, gitlab, confluence
    provider_user_id = Column(String(255), nullable=True, index=True)
    instance_id = Column(String(255), nullable=False, index=True)  # cloud_id для Jira
    instance_name = Column(String(255), nullable=True)
    instance_url = Column(String(500), nullable=True)
    access_token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    meta = Column(JSON, nullable=True)  # дополнительные данные
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="tokens")