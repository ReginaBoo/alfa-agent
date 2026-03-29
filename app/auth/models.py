from pydantic import BaseModel

class TokenData(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    scope: str