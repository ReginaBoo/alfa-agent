import requests
import json
from pprint import pprint

# =========================
# CONFIG
# =========================

JIRA_BASE_URL = "https://api.atlassian.com/ex/jira/***"

ACCESS_TOKEN = "***"  # Ваш токен доступа

HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/json"
}


# =========================
# HELPERS
# =========================

def jira_post(url: str, payload: dict):
    response = requests.post(
        url,
        headers=HEADERS,
        json=payload
    )

    print("\n====================")
    print("POST:", url)
    print("STATUS:", response.status_code)

    try:
        data = response.json()
        pprint(data)
    except Exception:
        print(response.text)
        data = None

    return response, data

def get_myself():
    url = f"{JIRA_BASE_URL}/rest/api/3/myself"

    response = requests.get(
        url,
        headers=HEADERS
    )

    print("\n====================")
    print("GET MYSELF")
    print("STATUS:", response.status_code)

    try:
        pprint(response.json())
    except Exception:
        print(response.text)

def get_permissions(project_key: str = None):
    # Valid permission keys for Jira Cloud API
    permissions = [
        "BROWSE_PROJECTS",      # Просмотр проектов
        "CREATE_ISSUES",        # Создание задач
        "EDIT_ISSUES",          # Редактирование
        "ASSIGN_ISSUES",        # Назначение
        "TRANSITION_ISSUES",    # Смена статуса
        "RESOLVE_ISSUES",       # Закрытие
        "SCHEDULE_ISSUES",      # Установка дедлайнов
    ]
    
    permissions_str = ",".join(permissions)
    url = f"{JIRA_BASE_URL}/rest/api/3/mypermissions?permissions={permissions_str}"
    
    if project_key:
        url += f"&projectKey={project_key}"
    
    response = requests.get(url, headers=HEADERS)
    print(f"\nGET PERMISSIONS — STATUS: {response.status_code}")
    pprint(response.json())


# =========================
# CREATE TEST ISSUES
# =========================

def create_test_issue(
    project_key: str,
    summary: str,
    issue_type: str = "Task",
    description: str = None,
    story_points: float = None,
    priority: str = "Medium",
    labels: list = None,
    due_date: str = None  # format: "2026-06-01"
):
    """Создаёт задачу в указанном проекте"""
    
    url = f"{JIRA_BASE_URL}/rest/api/3/issue"
    
    payload = {
        "fields": {
            "project": {"key": project_key},
            "summary": summary,
            "issuetype": {"name": issue_type},
            "priority": {"name": priority},
        }
    }
    
    if description:
        payload["fields"]["description"] = {
            "type": "doc",
            "version": 1,
            "content": [{
                "type": "paragraph",
                "content": [{"type": "text", "text": description}]
            }]
        }
    
    if story_points is not None:
        payload["fields"]["customfield_10016"] = story_points
    
    if labels:
        payload["fields"]["labels"] = labels
    
    if due_date:
        payload["fields"]["duedate"] = due_date
    
    response, data = jira_post(url, payload)
    
    if response.status_code == 201:
        issue_key = data.get("key")
        print(f"Created: {issue_key}")
        return issue_key
    return None

def get_project_issue_types(project_key: str):
    """Получает доступные типы задач для проекта"""
    url = f"{JIRA_BASE_URL}/rest/api/3/project/{project_key}"
    response = requests.get(url, headers=HEADERS)
    data = response.json()
    types = [t["name"] for t in data.get("issueTypes", []) if not t.get("subtask")]
    print(f"Available issue types in {project_key}: {types}")
    return types


def generate_test_data(project_key: str, prefix: str = "TEST"):
    """Создаёт набор тестовых задач для проверки метрик"""
    
    print(f"\nGenerating test data for project {project_key}...")
    
    test_issues = [
        # =========================
        # ЗАДАЧИ (Задача)
        # =========================
        {
            "summary": f"{prefix}: Small task",
            "issue_type": "Задача",  # ← было "Task"
            "story_points": 2,
            "priority": "Low",
        },
        {
            "summary": f"{prefix}: Medium task",
            "issue_type": "Задача",
            "story_points": 5,
            "priority": "Medium",
        },
        {
            "summary": f"{prefix}: Large task",
            "issue_type": "Задача",
            "story_points": 8,
            "priority": "High",
        },

        # =========================
        # ИСТОРИИ (История = Story)
        # =========================
        {
            "summary": f"{prefix}: User profile story",
            "issue_type": "История",  # ← было "Story"
            "story_points": 13,
            "priority": "High",
        },

        # =========================
        # БАГИ (Баг)
        # =========================
        {
            "summary": f"{prefix}: Critical login bug",
            "issue_type": "Баг",  # ← было "Bug"
            "story_points": 3,
            "priority": "Highest",
        },
        {
            "summary": f"{prefix}: Minor UI bug",
            "issue_type": "Баг",
            "story_points": 1,
            "priority": "Low",
        },

        # =========================
        # БЕЗ STORY POINTS (fallback на тип)
        # =========================
        {
            "summary": f"{prefix}: No SP task",
            "issue_type": "Задача",
            "story_points": None,  # Проверка ISSUE_TYPE_WEIGHTS
        },

        # =========================
        # ДЕДЛАЙНЫ (для SLA/Deadline Stability)
        # =========================
        {
            "summary": f"{prefix}: Due soon",
            "issue_type": "Задача",
            "story_points": 3,
            "due_date": "2026-05-20",
        },
        {
            "summary": f"{prefix}: Overdue task",
            "issue_type": "Задача",
            "story_points": 5,
            "due_date": "2026-05-10",  # Просрочено
        },

        # =========================
        # ЭПИК (высокий вес)
        # =========================
        {
            "summary": f"{prefix}: Feature epic",
            "issue_type": "Эпик",  # ← было "Epic"
            "story_points": 13,
            "priority": "High",
        },

        # =========================
        # МЕТКИ (для фильтрации)
        # =========================
        {
            "summary": f"{prefix}: Backend API task",
            "issue_type": "Задача",
            "story_points": 5,
            "labels": ["backend", "api"],
        },
        {
            "summary": f"{prefix}: Frontend UI task",
            "issue_type": "Задача",
            "story_points": 3,
            "labels": ["frontend", "ui"],
        },
    ]
    
    created = []
    for config in test_issues:
        # Создаём копию и добавляем общие метки
        issue_config = config.copy()
        base_labels = ["test-data", "auto-generated", prefix.lower()]
        existing_labels = issue_config.get("labels") or []
        issue_config["labels"] = base_labels + existing_labels
        
        labels = issue_config.pop("labels")
        
        key = create_test_issue(
            project_key=project_key,
            description=f"Auto-generated test data. Config: {config}",
            labels=labels,
            **issue_config
        )
        if key:
            created.append(key)
    
    print(f"\nCreated {len(created)} test issues: {created}")
    return created


def transition_issue(issue_key: str, transition_name: str):
    """Меняет статус задачи (для тестирования changelog)"""
    
    # 1. Получаем доступные транзиции
    url = f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}/transitions"
    response = requests.get(url, headers=HEADERS)
    transitions = response.json().get("transitions", [])
    
    # 2. Находим нужный переход по имени
    target = next((t for t in transitions if t["name"].lower() == transition_name.lower()), None)
    if not target:
        print(f"Transition '{transition_name}' not found. Available: {[t['name'] for t in transitions]}")
        return False
    
    # 3. Выполняем переход
    payload = {"transition": {"id": target["id"]}}
    url = f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}/transitions"
    response, data = jira_post(url, payload)
    
    if response.status_code == 204:
        print(f"Transitioned {issue_key} → {transition_name}")
        return True
    return False

if __name__ == "__main__":
    # 1. Проверка токена и прав
    get_myself()
    get_permissions(project_key="DEV")
    get_project_issue_types("DEV")
    # 2. Создание тестовых данных
    created_keys = generate_test_data(project_key="DEV", prefix="ALPHA")
    
    # 3. Тест смены статуса (для changelog)
    if created_keys:

        # TASK FLOW
        transition_issue(created_keys[0], "In Progress")
        transition_issue(created_keys[0], "Testing / QA")
        transition_issue(created_keys[0], "Готово")

        # STUCK IN PROGRESS
        transition_issue(created_keys[1], "In Progress")

        # QA FLOW
        transition_issue(created_keys[2], "In Progress")
        transition_issue(created_keys[2], "Testing / QA")

        # BUG Готово
        transition_issue(created_keys[4], "In Progress")
        transition_issue(created_keys[4], "Готово")
    
    # 4. Запуск синхронизации через бэкенд
    print("\nTriggering sync via backend...")
    import requests as req
    session_token = "***"  # SESSION_TOKEN
    
    resp = req.post(
        "http://localhost:8000/jira/sync-async/DEV?instance_name=reginaboo",
        cookies={"session_token": session_token}
    )

    print(f"Sync response: {resp.status_code} — {resp.json()}")