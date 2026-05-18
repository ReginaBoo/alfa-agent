# backend/scripts/02_create_test_projects.py

"""
Скрипт для создания тестовых проектов в Jira (без добавления пользователей)
Запуск: python scripts/02_create_test_projects.py

Что делает:
- Проверяет существование проектов
- Создаёт проекты, если их нет
- НЕ добавляет пользователей (они уже есть в Jira)
"""

import requests
import sys
import time
import json
import os
from datetime import datetime
from typing import Dict, Set

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import (
    JIRA_URL, ADMIN_EMAIL, API_TOKEN, MY_EMAIL,
    TEST_PROJECTS
)


def load_users() -> Dict[str, str]:
    """Загружает пользователей из файла"""
    users_file = os.path.join(os.path.dirname(__file__), '.test_users.json')
    if not os.path.exists(users_file):
        print("❌ Файл с пользователями не найден!")
        sys.exit(1)
    
    with open(users_file, 'r', encoding='utf-8') as f:
        users = json.load(f)
    return {user['email']: user['account_id'] for user in users}


def get_existing_projects() -> Set[str]:
    """Получает список существующих проектов"""
    url = f"{JIRA_URL}/rest/api/3/project"
    auth = (ADMIN_EMAIL, API_TOKEN)
    
    try:
        response = requests.get(url, auth=auth, timeout=30)
        if response.status_code == 200:
            return {p['key'] for p in response.json()}
        return set()
    except Exception:
        return set()


def create_jira_project(project_config: Dict, lead_account_id: str) -> bool:
    """Создаёт проект в Jira"""
    url = f"{JIRA_URL}/rest/api/3/project"
    auth = (ADMIN_EMAIL, API_TOKEN)
    
    payload = {
        "key": project_config['key'],
        "name": project_config['name'],
        "projectTypeKey": "software",
        "projectTemplateKey": "com.pyxis.greenhopper.jira:gh-simplified-agility-scrum",
        "description": project_config['description'],
        "leadAccountId": lead_account_id,
        "assigneeType": "PROJECT_LEAD"
    }
    
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    
    try:
        response = requests.post(url, json=payload, auth=auth, headers=headers, timeout=30)
        if response.status_code == 201:
            print(f"      ✅ Создан")
            return True
        elif response.status_code == 400 and "already exists" in response.text.lower():
            print(f"      ⚠️ Уже существует")
            return True
        else:
            print(f"      ❌ Ошибка {response.status_code}: {response.text[:100]}")
            return False
    except Exception as e:
        print(f"      ❌ Ошибка: {e}")
        return False


def main():
    print("=" * 60)
    print("🚀 СОЗДАНИЕ ТЕСТОВЫХ ПРОЕКТОВ")
    print("=" * 60)
    
    # Загружаем пользователей
    print("\n📂 Загрузка пользователей...")
    users_by_email = load_users()
    print(f"   ✅ Загружено {len(users_by_email)} пользователей")
    
    # Проверка подключения
    print("\n🔍 Проверка подключения...")
    try:
        test_response = requests.get(f"{JIRA_URL}/rest/api/3/serverInfo", 
                                      auth=(ADMIN_EMAIL, API_TOKEN), timeout=10)
        if test_response.status_code != 200:
            print(f"❌ Ошибка: {test_response.status_code}")
            return
        print("✅ Подключено")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return
    
    existing_projects = get_existing_projects()
    print(f"\n📁 Существующие проекты: {list(existing_projects) if existing_projects else 'нет'}")
    
    created = []
    
    for project_config in TEST_PROJECTS:
        project_key = project_config['key']
        print(f"\nПроект: {project_key} - {project_config['name']}")
        
        if project_key in existing_projects:
            print(f"   OK Уже существует")
            created.append(project_key)
        else:
            print(f"   Не найден, создаём...")
            # Все проекты создаются с вами как лидером
            lead_id = users_by_email.get(MY_EMAIL)
            if not lead_id:
                print(f"   WARN Ваш аккаунт не найден в созданных пользователях")
                print(f"   Попробуем найти ваш AccountId через API...")
                # Пробуем найти ваш аккаунт по email
                auth = (ADMIN_EMAIL, API_TOKEN)
                url = f"{JIRA_URL}/rest/api/3/user/search?query={MY_EMAIL}"
                try:
                    resp = requests.get(url, auth=auth, timeout=30)
                    if resp.status_code == 200:
                        users = resp.json()
                        if users:
                            lead_id = users[0].get('accountId')
                            print(f"   OK Найдён ваш AccountId: {lead_id}")
                        else:
                            print(f"   ERR Ваш аккаунт не найден в Jira!")
                            continue
                except Exception as e:
                    print(f"   ERR Ошибка поиска: {e}")
                    continue
            
            if create_jira_project(project_config, lead_id):
                created.append(project_key)
                time.sleep(2)
    
    # Сохраняем результат
    result = {
        "projects": created,
        "total": len(created),
        "created_at": datetime.now().isoformat()
    }
    
    os.makedirs('scripts', exist_ok=True)
    with open('scripts/.test_projects.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print("\n" + "=" * 60)
    print("📊 ИТОГИ")
    print("=" * 60)
    print(f"\n✅ Проектов: {len(created)}")
    for p in created:
        print(f"   - {p}")


if __name__ == "__main__":
    main()