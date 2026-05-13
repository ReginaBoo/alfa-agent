"""
Pydantic модели для GitHub API.
"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class GitHubUser(BaseModel):
    """Модель пользователя GitHub"""
    login: str
    id: int
    avatar_url: Optional[str] = None
    html_url: Optional[str] = None
    type: Optional[str] = None


class GitHubRepo(BaseModel):
    """Модель репозитория GitHub"""
    id: int
    name: str
    full_name: str
    owner: Optional[GitHubUser] = None
    html_url: Optional[str] = None
    description: Optional[str] = None
    private: Optional[bool] = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    pushed_at: Optional[str] = None


class GitHubLabel(BaseModel):
    """Модель лейбла GitHub"""
    id: int
    name: str
    color: Optional[str] = None
    description: Optional[str] = None


class GitHubAssignee(BaseModel):
    """Модель назначенного пользователя"""
    login: str
    id: int
    avatar_url: Optional[str] = None
    html_url: Optional[str] = None


class GitHubMilestone(BaseModel):
    """Модель вехи (milestone) GitHub"""
    id: int
    number: int
    title: str
    description: Optional[str] = None
    state: Optional[str] = None
    due_on: Optional[str] = None
    html_url: Optional[str] = None


class GitHubIssue(BaseModel):
    """Модель issue GitHub"""
    id: int
    number: int
    title: str
    user: Optional[GitHubUser] = None
    state: str
    locked: bool = False
    labels: List[GitHubLabel] = []
    assignees: List[GitHubAssignee] = []
    milestone: Optional[GitHubMilestone] = None
    comments: int = 0
    created_at: str
    updated_at: str
    closed_at: Optional[str] = None
    author_association: Optional[str] = None
    body: Optional[str] = None
    html_url: str
    repository_url: str
    
    # Дополнительные поля из API
    pull_request: Optional[dict] = None
    closed_by: Optional[GitHubUser] = None


class GitHubIssueEvent(BaseModel):
    """Модель события issue GitHub"""
    id: int
    event: str  # assigned, unassigned, labeled, unlabeled, mentioned, closed, opened, etc.
    actor: Optional[GitHubUser] = None
    created_at: str
    commit_id: Optional[str] = None
    commit_url: Optional[str] = None
    assignee: Optional[GitHubAssignee] = None
    label: Optional[GitHubLabel] = None
    rename: Optional[dict] = None  # для rename событий (изменение заголовка)
    state: Optional[str] = None
    milestone: Optional[GitHubMilestone] = None
    performed_via_github_app: Optional[dict] = None


class GitHubComment(BaseModel):
    """Модель комментария к issue"""
    id: int
    body: str
    user: Optional[GitHubUser] = None
    created_at: str
    updated_at: str
    html_url: str
