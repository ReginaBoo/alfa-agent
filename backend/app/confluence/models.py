# app/confluence/models.py
from datetime import datetime
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field


class ConfluenceUser(BaseModel):
    account_id: str = Field(..., alias="accountId")
    display_name: str = Field(..., alias="displayName")
    email: Optional[str] = None
    profile_picture: Optional[str] = Field(None, alias="profilePicture")


class ConfluencePageVersion(BaseModel):
    """Версия страницы"""
    number: int
    message: str = ""
    minor_edit: bool = Field(False, alias="minorEdit")
    author_id: Optional[str] = Field(None, alias="authorId")
    created_at: Optional[datetime] = Field(None, alias="createdAt")
    ncs_step_version: Optional[str] = Field(None, alias="ncsStepVersion")


class ConfluencePage(BaseModel):
    """Страница Confluence (API v2)"""
    id: str
    title: str
    status: str = "current"
    space_id: str = Field(..., alias="spaceId")
    parent_id: Optional[str] = Field(None, alias="parentId")
    parent_type: Optional[str] = Field(None, alias="parentType")
    position: Optional[int] = None
    author_id: Optional[str] = Field(None, alias="authorId")
    owner_id: Optional[str] = Field(None, alias="ownerId")
    last_owner_id: Optional[str] = Field(None, alias="lastOwnerId")
    created_at: Optional[datetime] = Field(None, alias="createdAt")
    version: ConfluencePageVersion
    body: Optional[Dict[str, Any]] = {}
    links: Optional[Dict[str, str]] = Field(None, alias="_links")
    
    class Config:
        populate_by_name = True
        validate_by_name = True  # вместо allow_population_by_field_name


class ConfluenceSpace(BaseModel):
    id: str
    key: str
    name: str
    type: str
    status: str
