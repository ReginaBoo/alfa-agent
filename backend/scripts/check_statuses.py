# backend/scripts/check_statuses.py
import requests
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import JIRA_URL, ADMIN_EMAIL, API_TOKEN

def check_project_statuses(project_key):
    auth = (ADMIN_EMAIL, API_TOKEN)
    
    # Получаем статусы для проекта
    url = f"{JIRA_URL}/rest/api/3/project/{project_key}/statuses"
    
    try:
        resp = requests.get(url, auth=auth, timeout=30)
        if resp.status_code == 200:
            print(f"\n📋 Статусы для {project_key}:")
            for issue_type in resp.json():
                print(f"   Тип: {issue_type.get('name')}")
                for status in issue_type.get('statuses', []):
                    print(f"      - {status.get('name')}")
        else:
            print(f"\n⚠️ {project_key}: {resp.status_code}")
    except Exception as e:
        print(f"Ошибка: {e}")

if __name__ == "__main__":
    print("🔍 Проверка статусов в проектах...")
    for project in ["HEALTH", "CRUNCH", "IMBAL", "KANBAN"]:
        check_project_statuses(project)