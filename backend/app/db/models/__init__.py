# app/db/__init__.py

from app.db.base import Base

# Сначала identity (нет внешних зависимостей)
from app.db.models.identity import User, Session, IntegrationToken

# Потом core (зависит от identity)
from app.db.models.core import Project, UserProject

# Потом raw
from app.db.models.raw import RawEvent

# Потом normalized
from app.db.models.normalized import (
    JiraIssue, IssueChangelog, ProjectStatusMapping,
    ConfluencePage, ConfluencePageVersion, ConfluenceComment,
    GithubIssue, GithubIssueEvent
)

# Потом metrics
from app.db.models.metrics import MetricRaw, UserMetric, ProjectMetric, ProjectHealth