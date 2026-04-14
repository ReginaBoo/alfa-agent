# app/confluence/models.py
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field


class ConfluenceUser(BaseModel):
    account_id: str = Field(..., alias="accountId")
    display_name: str = Field(..., alias="displayName")
    email: Optional[str] = None
    profile_picture: Optional[str] = Field(None, alias="profilePicture")


class ConfluenceSpace(BaseModel):
    id: str
    key: str
    name: str
    type: str  # "global", "personal"
    status: str  # "current", "archived"


class ConfluencePageVersion(BaseModel):
    number: int
    when: datetime
    message: Optional[str] = None
    by: Optional[ConfluenceUser] = None


class ConfluencePage(BaseModel):
    id: str
    title: str
    type: str  # "page", "blogpost"
    status: str  # "current", "draft", "trashed"
    space: ConfluenceSpace
    version: ConfluencePageVersion
    created: datetime
    updated: datetime
    author: Optional[ConfluenceUser] = None
    
    # Содержимое — может быть в разных форматах
    body: Optional[dict] = None  # format="storage" (raw HTML-like)
    view_body: Optional[str] = None  # format="view" (rendered HTML)
    
    # Ссылки
    links: Optional[dict] = None
    
    @property
    def url(self) -> Optional[str]:
        """Получаем прямой URL на страницу"""
        if self.links and self.links.get("webui"):
            return self.links["webui"]
        return None