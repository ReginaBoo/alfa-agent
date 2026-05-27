# tests/fixtures/mock_responses.py

"""
Моки для внешних API
"""


MOCK_JIRA_PROJECTS = [
    {
        "id": "10000",
        "key": "SCRUM",
        "name": "Scrum Project",
        "projectTypeKey": "software",
        "avatarUrls": {
            "48x48": "https://example.com/avatar.png"
        }
    },
    {
        "id": "10001",
        "key": "TEST",
        "name": "Test Project",
        "projectTypeKey": "business"
    }
]


MOCK_JIRA_ISSUES = {
    "issues": [
        {
            "id": "10001",
            "key": "SCRUM-1",
            "fields": {
                "summary": "Implement login feature",
                "status": {"name": "In Progress", "id": "3"},
                "priority": {"name": "High", "id": "2"},
                "issuetype": {"name": "Story", "id": "10001"},
                "assignee": {
                    "accountId": "12345",
                    "displayName": "John Doe",
                    "emailAddress": "john@example.com"
                },
                "customfield_10016": 5,  # Story Points
                "created": "2024-01-01T10:00:00.000+0000",
                "updated": "2024-01-15T15:30:00.000+0000",
                "duedate": "2024-01-31"
            }
        },
        {
            "id": "10002",
            "key": "SCRUM-2",
            "fields": {
                "summary": "Fix login bug",
                "status": {"name": "Done", "id": "10000"},
                "priority": {"name": "Highest", "id": "1"},
                "issuetype": {"name": "Bug", "id": "10002"},
                "assignee": {
                    "accountId": "12345",
                    "displayName": "John Doe",
                    "emailAddress": "john@example.com"
                },
                "customfield_10016": 3,  # Story Points
                "created": "2024-01-10T10:00:00.000+0000",
                "updated": "2024-01-20T15:30:00.000+0000",
                "resolutiondate": "2024-01-20T15:30:00.000+0000"
            }
        }
    ],
    "total": 2,
    "maxResults": 50,
    "startAt": 0
}


MOCK_JIRA_CHANGELOG = {
    "values": [
        {
            "id": "10001",
            "created": "2024-01-15T10:00:00.000+0000",
            "author": {
                "accountId": "12345",
                "displayName": "John Doe"
            },
            "items": [
                {
                    "field": "status",
                    "fromString": "To Do",
                    "toString": "In Progress"
                }
            ]
        },
        {
            "id": "10002",
            "created": "2024-01-20T10:00:00.000+0000",
            "author": {
                "accountId": "12345",
                "displayName": "John Doe"
            },
            "items": [
                {
                    "field": "status",
                    "fromString": "In Progress",
                    "toString": "Done"
                }
            ]
        }
    ],
    "total": 2
}


def mock_jira_api_response(endpoint: str, method: str = "GET"):
    """Возвращает мок ответ для Jira API"""
    
    if "project" in endpoint and method == "GET":
        return MOCK_JIRA_PROJECTS
    
    if "search" in endpoint and method == "GET":
        return MOCK_JIRA_ISSUES
    
    if "changelog" in endpoint and method == "GET":
        return MOCK_JIRA_CHANGELOG
    
    return {}