"""Схема raw — сырые события из внешних систем"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, JSON, Index
from app.db.base import Base


class RawEvent(Base):
    __tablename__ = "raw_events"
    __table_args__ = (
        Index("idx_raw_events_source_external", "source", "external_id"),
        Index("idx_raw_events_timestamp", "timestamp"),
        {"schema": "raw"}
    )
    
    id = Column(Integer, primary_key=True)
    source = Column(String(50), nullable=False, index=True)  # jira, confluence, github
    event_type = Column(String(100), nullable=False, index=True)  # issue, project, page, commit
    external_id = Column(String(255), nullable=False, index=True)
    project_integration_id = Column(Integer, nullable=True)
    payload = Column(JSON, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)