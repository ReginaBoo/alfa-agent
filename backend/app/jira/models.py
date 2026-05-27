# app/jira/models.py

"""
Pydantic models for Jira API responses.
Типизированное представление данных из Jira REST API v3.
"""

from datetime import datetime
from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field, field_validator


class JiraUser(BaseModel):
    """Пользователь Jira (исполнитель, автор, репортёр)"""
    account_id: str = Field(..., alias="accountId")
    display_name: str = Field(..., alias="displayName")
    email: Optional[str] = None
    avatar_url: Optional[str] = Field(None, alias="avatarUrls")
    
    @field_validator("avatar_url", mode="before")
    @classmethod
    def extract_avatar_url(cls, v: Any) -> Optional[str]:
        """Извлекаем URL аватара из словаря avatarUrls"""
        if isinstance(v, dict):
            return v.get("48x48") or v.get("24x24") or v.get("16x16")
        return v


class JiraStatus(BaseModel):
    """Статус задачи"""
    id: str
    name: str
    status_category: Optional[str] = Field(None, alias="statusCategory")
    
    @field_validator("status_category", mode="before")
    @classmethod
    def extract_category_name(cls, v: Any) -> Optional[str]:
        if isinstance(v, dict):
            return v.get("name")
        return v


class JiraPriority(BaseModel):
    """Приоритет задачи"""
    id: str
    name: str
    icon_url: Optional[str] = Field(None, alias="iconUrl")


class JiraIssueType(BaseModel):
    """Тип задачи (Epic, Story, Task, Bug, Sub-task)"""
    id: str
    name: str
    description: Optional[str] = None
    subtask: bool = False


class JiraIssueFields(BaseModel):
    """Поля задачи Jira"""
    summary: str
    status: JiraStatus
    assignee: Optional[JiraUser] = None
    reporter: Optional[JiraUser] = None
    priority: Optional[JiraPriority] = None
    issuetype: JiraIssueType
    created: datetime
    updated: datetime
    duedate: Optional[datetime] = None
    resolutiondate: Optional[datetime] = None
    
    # Story Points — может быть в разных кастомных полях
    customfield_10002: Optional[float] = Field(None, alias="customfield_10002")
    customfield_10016: Optional[float] = Field(None, alias="customfield_10016")
    
    # 👇 ДОБАВИТЬ ЭТИ ПОЛЯ
    # Timetracking (учёт времени)
    timetracking: Optional[Dict[str, Any]] = None
    aggregatetimespent: Optional[int] = Field(None, alias="aggregatetimespent")
    aggregatetimeestimate: Optional[int] = Field(None, alias="aggregatetimeestimate")
    timeoriginalestimate: Optional[int] = Field(None, alias="timeoriginalestimate")
    timespent: Optional[int] = Field(None, alias="timespent")
    # 👆 КОНЕЦ ДОБАВЛЕННЫХ ПОЛЕЙ
    
    # Для связи с Git (ключ задачи в сообщении коммита)
    labels: List[str] = Field(default_factory=list)
    
    # Для связи с Confluence (ссылки в описании)
    description: Optional[str] = None
    
    @property
    def story_points(self) -> Optional[float]:
        """Получаем Story Points из любого кастомного поля"""
        if self.customfield_10002 is not None:
            return self.customfield_10002
        if self.customfield_10016 is not None:
            return self.customfield_10016
        return None
    
    @property
    def is_open(self) -> bool:
        """Задача в открытом статусе? (не Done и не Closed)"""
        closed_categories = {"done", "closed"}
        category = self.status.status_category
        if category:
            return category.lower() not in closed_categories
        return self.status.name.lower() not in ("done", "closed", "resolved")


class JiraIssue(BaseModel):
    """Задача Jira (полная)"""
    id: str
    key: str
    fields: JiraIssueFields
    self_url: Optional[str] = Field(None, alias="self")
    
    # Ссылки на связанные задачи
    subtasks: List[Dict[str, Any]] = Field(default_factory=list)
    issuelinks: List[Dict[str, Any]] = Field(default_factory=list)
    
    @property
    def story_points(self) -> Optional[float]:
        return self.fields.story_points
    
    @property
    def assignee_name(self) -> Optional[str]:
        if self.fields.assignee:
            return self.fields.assignee.display_name
        return None
    
    @property
    def assignee_account_id(self) -> Optional[str]:
        if self.fields.assignee:
            return self.fields.assignee.account_id
        return None


class JiraProject(BaseModel):
    """Проект Jira"""
    id: str
    key: str
    name: str
    url: Optional[str] = None
    avatar_url: Optional[str] = Field(None, alias="avatarUrls")
    
    @field_validator("avatar_url", mode="before")
    @classmethod
    def extract_avatar_url(cls, v: Any) -> Optional[str]:
        if isinstance(v, dict):
            return v.get("48x48") or v.get("32x32")
        return v


class JiraSearchResponse(BaseModel):
    """Ответ на поиск задач (JQL search)"""
    expand: Optional[str] = None
    start_at: int = Field(0, alias="startAt")
    max_results: int = Field(0, alias="maxResults")
    total: int = 0
    issues: List[JiraIssue] = Field(default_factory=list)


class JiraChangelogItem(BaseModel):
    """Элемент истории изменений (поле и его значение)"""
    field: str
    fieldtype: str
    from_string: Optional[str] = Field(None, alias="fromString")
    to_string: Optional[str] = Field(None, alias="toString")


class JiraChangelogEntry(BaseModel):
    """Запись в истории изменений задачи"""
    id: str
    author: Optional[JiraUser] = None
    created: datetime
    items: List[JiraChangelogItem] = Field(default_factory=list)


class JiraChangelogResponse(BaseModel):
    """Ответ с историей изменений"""
    values: List[JiraChangelogEntry] = Field(default_factory=list)
    total: int = 0