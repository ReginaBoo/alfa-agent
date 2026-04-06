from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import requests

from app.db.session import get_db
from app.db.models import IntegrationToken
from app.core.dependencies import get_current_user

from typing import Optional, List
from pydantic import BaseModel

router = APIRouter()


# ================= HELPERS =================

def get_token(instance_name: str, db: Session, user_id: int) -> IntegrationToken:
    token = db.query(IntegrationToken).filter(
        IntegrationToken.instance_name == instance_name,
        IntegrationToken.user_id == user_id,
        IntegrationToken.provider == "jira"
    ).first()

    if not token:
        raise HTTPException(status_code=404, detail="Jira site not found")

    return token


def jira_url(token: IntegrationToken, path: str) -> str:
    # Используем правильный URL для OAuth 2.0
    return f"https://api.atlassian.com/ex/jira/{token.instance_id}/rest/api/3/{path}"


def jira_headers(token: IntegrationToken) -> dict:
    return {
        "Authorization": f"Bearer {token.access_token}",
        "Content-Type": "application/json"
    }


# ================= SITES =================

@router.get("/sites")
def get_sites(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    tokens = db.query(IntegrationToken).filter(
        IntegrationToken.user_id == current_user.id,
        IntegrationToken.provider == "jira"
    ).all()

    return {
        "success": True,
        "sites": [
            {
                "cloud_id": t.instance_id,
                "site_name": t.instance_name,
                "site_url": t.instance_url,
                "expires_at": t.expires_at.isoformat() if t.expires_at else None
            }
            for t in tokens
        ]
    }


# ================= PROJECTS =================

@router.get("/projects")
def get_projects(
    instance_name: str = Query(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    token = get_token(instance_name, db, current_user.id)

    try:
        response = requests.get(
            jira_url(token, "project"),
            headers=jira_headers(token),
            timeout=10
        )
        response.raise_for_status()

        projects = response.json()

        return {
            "success": True,
            "site": {
                "cloud_id": token.instance_id,
                "url": token.instance_url,
                "name": token.instance_name
            },
            "total_projects": len(projects),
            "projects": [
                {
                    "id": p.get("id"),
                    "key": p.get("key"),
                    "name": p.get("name"),
                    "url": p.get("self")
                }
                for p in projects
            ]
        }

    except requests.exceptions.RequestException as e:
        raise HTTPException(502, f"Jira API error: {str(e)}")


# ================= MODELS =================

class CreateIssueRequest(BaseModel):
    project_key: str
    summary: str
    issue_type: str = "Task"
    description: Optional[str] = None
    assignee_account_id: Optional[str] = None
    priority: Optional[str] = None
    labels: Optional[List[str]] = None


class TransitionRequest(BaseModel):
    transition_id: str


# ================= ISSUES (НОВЫЙ ЭНДПОИНТ) =================

@router.get("/issues")
def search_issues(
    instance_name: str = Query(...),
    jql: str = Query(...),
    start_at: int = Query(0, ge=0),
    max_results: int = Query(50, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    token = get_token(instance_name, db, current_user.id)

    try:
        # НОВЫЙ ЭНДПОИНТ: search/jql вместо search
        response = requests.get(
            f"https://api.atlassian.com/ex/jira/{token.instance_id}/rest/api/3/search/jql",
            headers=jira_headers(token),
            params={
                "jql": jql,
                "startAt": start_at,
                "maxResults": max_results
            },
            timeout=10
        )
        response.raise_for_status()

        data = response.json()

        return {
            "success": True,
            "total": data.get("total", 0),
            "is_last": data.get("isLast", True),
            "issues": data.get("issues", [])
        }

    except requests.exceptions.RequestException as e:
        raise HTTPException(502, f"Jira API error: {str(e)}")


@router.get("/issues/{issue_key}")
def get_issue(
    issue_key: str,
    instance_name: str = Query(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    token = get_token(instance_name, db, current_user.id)

    try:
        response = requests.get(
            jira_url(token, f"issue/{issue_key}"),
            headers=jira_headers(token),
            timeout=10
        )
        response.raise_for_status()

        return {
            "success": True,
            "issue": response.json()
        }

    except requests.exceptions.RequestException as e:
        raise HTTPException(502, f"Jira API error: {str(e)}")


@router.post("/issues")
def create_issue(
    instance_name: str = Query(...),
    issue_data: CreateIssueRequest = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    token = get_token(instance_name, db, current_user.id)

    payload = {
        "fields": {
            "project": {"key": issue_data.project_key},
            "summary": issue_data.summary,
            "issuetype": {"name": issue_data.issue_type}
        }
    }

    if issue_data.description:
        payload["fields"]["description"] = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": issue_data.description}
                    ]
                }
            ]
        }

    if issue_data.assignee_account_id:
        payload["fields"]["assignee"] = {"accountId": issue_data.assignee_account_id}

    if issue_data.priority:
        payload["fields"]["priority"] = {"name": issue_data.priority}

    if issue_data.labels:
        payload["fields"]["labels"] = issue_data.labels

    try:
        response = requests.post(
            jira_url(token, "issue"),
            headers=jira_headers(token),
            json=payload,
            timeout=10
        )
        response.raise_for_status()

        result = response.json()

        return {
            "success": True,
            "issue_key": result.get("key"),
            "issue_id": result.get("id")
        }

    except requests.exceptions.RequestException as e:
        raise HTTPException(502, f"Jira API error: {str(e)}")


@router.post("/issues/{issue_key}/transitions")
def transition_issue(
    issue_key: str,
    instance_name: str = Query(...),
    transition: TransitionRequest = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    token = get_token(instance_name, db, current_user.id)

    try:
        response = requests.post(
            jira_url(token, f"issue/{issue_key}/transitions"),
            headers=jira_headers(token),
            json={"transition": {"id": transition.transition_id}},
            timeout=10
        )
        response.raise_for_status()

        return {"success": True}

    except requests.exceptions.RequestException as e:
        raise HTTPException(502, f"Jira API error: {str(e)}")


@router.get("/issues/{issue_key}/changelog")
def get_issue_changelog(
    issue_key: str,
    instance_name: str = Query(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    token = get_token(instance_name, db, current_user.id)

    try:
        response = requests.get(
            jira_url(token, f"issue/{issue_key}/changelog"),
            headers=jira_headers(token),
            timeout=10
        )
        response.raise_for_status()

        return {
            "success": True,
            "changelog": response.json()
        }

    except requests.exceptions.RequestException as e:
        raise HTTPException(502, f"Jira API error: {str(e)}")