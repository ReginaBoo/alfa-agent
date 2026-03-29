from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import requests

from app.db.session import get_db
from app.db.models import Token

router = APIRouter()
USER_ID = "test_user"

def get_current_token(db: Session = Depends(get_db)):
    token = db.query(Token).filter(Token.user_id == USER_ID).first()
    if not token:
        raise HTTPException(status_code=401, detail="No token found in database")
    return token

@router.get("/projects")
def get_projects(token=Depends(get_current_token)):
    # Получаем cloudId
    res = requests.get(
        "https://api.atlassian.com/oauth/token/accessible-resources",
        headers={"Authorization": f"Bearer {token.access_token}"}
    ).json()
    cloud_id = res[0]["id"]
    
    # Получаем проекты Jira
    projects = requests.get(
        f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/2/project",
        headers={"Authorization": f"Bearer {token.access_token}"}
    ).json()
    
    return projects