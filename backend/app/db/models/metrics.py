# app/db/models/metrics.py

from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, ForeignKey
from sqlalchemy.sql import func
from datetime import datetime

from app.db.timescale import TimescaleBase


class MetricRaw(TimescaleBase):
    """Сырые метрики во времени (гипертаблица TimescaleDB)"""
    __tablename__ = "metrics_raw"
    __table_args__ = {"schema": "public"}
    
    time = Column(DateTime, primary_key=True, server_default=func.now())
    project_id = Column(Integer, nullable=False)
    user_id = Column(Integer, nullable=True)
    metric_name = Column(String(100), nullable=False)
    value = Column(Float, nullable=False)
    dimensions = Column(JSON, nullable=True)  # {"team": "backend", "sprint": "Sprint 1"}
    metric_version = Column(String(20), default="1.0")
    is_final = Column(Integer, default=1)  # 1 = финальное, 0 = промежуточное


class UserMetric(TimescaleBase):
    """Агрегированные метрики по пользователям"""
    __tablename__ = "user_metrics"
    __table_args__ = {"schema": "public"}
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    project_id = Column(Integer, nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    workload_index = Column(Float, nullable=True)
    activity_score = Column(Float, nullable=True)
    tasks_completed = Column(Integer, default=0)
    commits_count = Column(Integer, default=0)
    sla_score = Column(Float, nullable=True)
    calculated_at = Column(DateTime, server_default=func.now())


class ProjectMetric(TimescaleBase):
    """Агрегированные метрики по проектам"""
    __tablename__ = "project_metrics"
    __table_args__ = {"schema": "public"}
    
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    issues_created = Column(Integer, default=0)
    issues_closed = Column(Integer, default=0)
    sla_score = Column(Float, nullable=True)
    stability_score = Column(Float, nullable=True)
    deadline_stability = Column(Float, nullable=True)
    calculated_at = Column(DateTime, server_default=func.now())


class ProjectHealth(TimescaleBase):
    __tablename__ = "project_health"
    __table_args__ = {"schema": "public"}
    
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    health_score = Column(Float, nullable=False)
    status = Column(String(20), nullable=False)
    metric_type = Column(String(50), nullable=False, default="project_health")  # ← добавить
    calculated_at = Column(DateTime, server_default=func.now())