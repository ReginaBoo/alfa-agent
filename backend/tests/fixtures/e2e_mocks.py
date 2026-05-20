"""
Моки для E2E тестов — позволяют тестировать без реальных внешних сервисов.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any


# ================= JIRA MOCKS =================

def mock_jira_project(key: str = "HEALTH", name: str = "Health Project") -> Dict[str, Any]:
    """Mock проекта Jira"""
    return {
        "id": "10001",
        "key": key,
        "name": name,
        "projectTypeKey": "software",
        "isPrivate": False,
        "avatarUrls": {"48x48": "https://example.com/avatar.png"},
        "self": f"https://api.atlassian.com/ex/jira/test/rest/api/3/project/{key}"
    }


def mock_jira_issue(
    key: str = "HEALTH-1",
    status: str = "To Do",
    assignee: str = "test-user-1",
    story_points: float = 5.0,
    issue_type: str = "Task",
    created_days_ago: int = 7
) -> Dict[str, Any]:
    """Mock задачи Jira"""
    created = datetime.utcnow() - timedelta(days=created_days_ago)
    updated = datetime.utcnow()
    
    return {
        "id": "10001",
        "key": key,
        "fields": {
            "summary": f"Test Issue {key}",
            "status": {
                "id": "10000",
                "name": status,
                "statusCategory": {
                    "id": 2,
                    "key": "in-progress" if status == "In Progress" else "todo",
                    "name": "In Progress" if status == "In Progress" else "To Do"
                }
            },
            "assignee": {
                "accountId": assignee,
                "displayName": f"Test User {assignee}",
                "emailAddress": f"{assignee}@test.com"
            },
            "reporter": {
                "accountId": "reporter-1",
                "displayName": "Reporter"
            },
            "priority": {"id": "3", "name": "Medium"},
            "issuetype": {"id": "10001", "name": issue_type, "subtask": False},
            "created": created.isoformat(),
            "updated": updated.isoformat(),
            "customfield_10016": story_points,  # Story Points
            "timetracking": {
                "originalEstimateSeconds": 36000,  # 10 hours
                "timeSpentSeconds": 7200,  # 2 hours
                "remainingEstimateSeconds": 28800  # 8 hours
            },
            "description": "Test issue description"
        },
        "changelog": {
            "values": [
                {
                    "id": "10001",
                    "author": {"accountId": assignee},
                    "created": created.isoformat(),
                    "items": [
                        {
                            "field": "status",
                            "fieldtype": "jira",
                            "from": None,
                            "fromString": None,
                            "to": "10000",
                            "toString": status
                        }
                    ]
                }
            ]
        }
    }


def mock_jira_statuses(project_key: str) -> List[Dict[str, Any]]:
    """Mock статусов проекта Jira"""
    return [
        {
            "issueType": "Task",
            "statuses": [
                {
                    "id": "10000",
                    "name": "Backlog",
                    "statusCategory": {"id": 2, "key": "todo", "name": "To Do"}
                },
                {
                    "id": "10001",
                    "name": "To Do",
                    "statusCategory": {"id": 2, "key": "todo", "name": "To Do"}
                },
                {
                    "id": "10002",
                    "name": "In Progress",
                    "statusCategory": {"id": 4, "key": "in-progress", "name": "In Progress"}
                },
                {
                    "id": "10003",
                    "name": "Done",
                    "statusCategory": {"id": 3, "key": "done", "name": "Done"}
                }
            ]
        }
    ]


# ================= CONFLUENCE MOCKS =================

def mock_confluence_space(
    space_id: str = "10001",
    key: str = "HEALTH",
    name: str = "Health Space"
) -> Dict[str, Any]:
    """Mock пространства Confluence"""
    return {
        "id": space_id,
        "key": key,
        "name": name,
        "type": "global",
        "status": "current"
    }


def mock_confluence_page(
    page_id: str = "10001",
    title: str = "Test Page",
    space_id: str = "10001"
) -> Dict[str, Any]:
    """Mock страницы Confluence"""
    return {
        "id": page_id,
        "title": title,
        "status": "current",
        "spaceId": space_id,
        "version": {
            "number": 1,
            "message": "Initial version",
            "authorId": "test-user-1",
            "createdAt": datetime.utcnow().isoformat()
        }
    }


# ================= GITHUB MOCKS =================

def mock_github_repo(
    full_name: str = "testuser/test-repo",
    repo_id: int = 123456
) -> Dict[str, Any]:
    """Mock репозитория GitHub"""
    return {
        "id": repo_id,
        "name": "test-repo",
        "full_name": full_name,
        "private": False,
        "owner": {
            "login": "testuser",
            "id": 12345,
            "type": "User"
        },
        "html_url": f"https://github.com/{full_name}",
        "description": "Test repository",
        "created_at": (datetime.utcnow() - timedelta(days=365)).isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "pushed_at": datetime.utcnow().isoformat()
    }


def mock_github_issue(
    number: int = 1,
    title: str = "Test Issue",
    state: str = "open"
) -> Dict[str, Any]:
    """Mock issue GitHub"""
    return {
        "id": 123456,
        "number": number,
        "title": title,
        "state": state,
        "locked": False,
        "labels": [],
        "assignees": [],
        "user": {
            "login": "testuser",
            "id": 12345
        },
        "created_at": (datetime.utcnow() - timedelta(days=7)).isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "closed_at": None,
        "comments": 0,
        "body": "Test issue body",
        "html_url": f"https://github.com/testuser/test-repo/issues/{number}"
    }


# ================= API RESPONSES =================

def mock_health_response(
    postgres_ok: bool = True,
    timescaledb_ok: bool = True,
    redis_ok: bool = False
) -> Dict[str, Any]:
    """Mock ответа /health"""
    return {
        "success": True,
        "data": {
            "status": "healthy" if all([postgres_ok, timescaledb_ok]) else "degraded",
            "services": {
                "postgres": {"ok": postgres_ok, "error": None if postgres_ok else "Connection failed"},
                "timescaledb": {"ok": timescaledb_ok, "error": None if timescaledb_ok else "Connection failed"},
                "redis": {"ok": redis_ok, "error": None if redis_ok else "Connection failed"}
            }
        },
        "meta": {"timestamp": datetime.utcnow().isoformat()}
    }


def mock_jira_projects_response(projects: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Mock ответа /jira/projects"""
    if projects is None:
        projects = [mock_jira_project()]
    
    return {
        "success": True,
        "total_projects": len(projects),
        "projects": [
            {"id": p["id"], "key": p["key"], "name": p["name"]}
            for p in projects
        ]
    }


def mock_sync_response(
    created: int = 0,
    updated: int = 0,
    total: int = 0
) -> Dict[str, Any]:
    """Mock ответа синхронизации"""
    return {
        "success": True,
        "message": f"Synced {total} issues",
        "details": {
            "created": created,
            "updated": updated,
            "total": total,
            "project_key": "HEALTH"
        }
    }


def mock_job_status_response(
    job_id: str = "test-job-id",
    status: str = "finished",
    result: Any = None,
    error: str = None
) -> Dict[str, Any]:
    """Mock ответа статуса задачи RQ"""
    response = {
        "success": True,
        "data": {
            "job_id": job_id,
            "status": status,
            "created_at": datetime.utcnow().isoformat(),
            "started_at": datetime.utcnow().isoformat() if status in ["started", "finished"] else None,
            "ended_at": datetime.utcnow().isoformat() if status == "finished" else None,
        }
    }
    
    if status == "finished" and result:
        response["data"]["result"] = result
    elif status == "failed" and error:
        response["data"]["error"] = error
    
    return response


# ================= METRICS MOCKS =================

def mock_workload_summary(
    project_key: str = "HEALTH",
    team_wi: float = 0.85,
    balance: float = 0.25
) -> Dict[str, Any]:
    """Mock Workload Index summary"""
    return [
        {
            "project_key": project_key,
            "project_name": "Health Project",
            "team_wi": team_wi,
            "team_wi_percent": team_wi * 100,
            "balance": balance,
            "balance_alert": balance > 0.5,
            "status": "optimal" if 0.7 <= team_wi <= 1.0 else "elevated" if team_wi > 1.0 else "underloaded",
            "status_text": "Оптимальная загрузка",
            "color": "green",
            "team_size": 3,
            "members": [
                {
                    "assignee_account_id": f"user-{i}",
                    "workload_index": team_wi + (i * 0.1) - 0.1,
                    "status": "optimal",
                    "status_text": "Оптимальная загрузка"
                }
                for i in range(3)
            ]
        }
    ]


def mock_health_score(
    health_score: float = 75.5,
    status: str = "yellow",
    sla_score: float = 80.0,
    stability_score: float = 70.0,
    balance_score: float = 85.0,
    deadline_score: float = 72.0
) -> Dict[str, Any]:
    """Mock Health Score"""
    return {
        "health_score": health_score,
        "status": status,
        "status_text": "Есть риск" if status == "yellow" else "Здоров" if status == "green" else "Критично",
        "icon": "⚠️" if status == "yellow" else "✅" if status == "green" else "🚨",
        "components": {
            "sla": {"score": sla_score, "weight": 0.35, "total_closed": 10, "on_time": 8, "late": 2},
            "stability": {"score": stability_score, "weight": 0.30, "bug_ratio": 15.0, "open_bugs": 3},
            "workload_balance": {"score": balance_score, "weight": 0.20, "balance_value": 0.25, "team_size": 3},
            "deadline_stability": {"score": deadline_score, "weight": 0.15, "total_issues": 20, "changed": 5}
        }
    }
