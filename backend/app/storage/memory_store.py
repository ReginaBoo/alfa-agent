from typing import Dict
from app.auth.models import TokenData

user_tokens: Dict[str, TokenData] = {}

def save_token(user_id: str, token: TokenData):
    user_tokens[user_id] = token

def get_token(user_id: str) -> TokenData | None:
    return user_tokens.get(user_id)