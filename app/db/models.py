# backend/app/db/models.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
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
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    atlassian_account_id = Column(String, index=True, nullable=False)  # лучше сделать NOT NULL
    cloud_id = Column(String, index=True, nullable=False)
    site_url = Column(String, nullable=True)  # может быть пустым, если не удалось получить
    site_name = Column(String, nullable=True)  # человекочитаемое имя (опционально)
    access_token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=False)
    expires_at = Column(DateTime, index=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="tokens")


class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    session_token = Column(String, unique=True, index=True)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="sessions")  # ← добавить