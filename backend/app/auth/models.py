from pydantic import BaseModel
from typing import Optional


class TokenData(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    scope: str
    token_type: str = "Bearer"

class AtlassianResource(BaseModel):
    id: str
    name: str
    url: str
    scopes: list[str]
    avatarUrl: str | None = None

class UserInfo(BaseModel):
    account_id: str
    email: Optional[str]
    display_name: Optional[str]
    picture: Optional[str]