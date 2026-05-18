# backend/scripts/01_create_test_users.py

#!/usr/bin/env python3
"""
Скрипт для создания тестовых пользователей в Jira Cloud
Запуск: python scripts/01_create_test_users.py

Требования:
- Права администратора Jira
- API токен из https://id.atlassian.com/manage-profile/security/api-tokens
"""

import requests
import sys
import time
import json
from typing import Dict, Optional, List
import os

# Добавляем путь к конфигу
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import (
    JIRA_URL, ADMIN_EMAIL, API_TOKEN, 
    TEST_USERS, BACKEND_URL
)


def create_jira_user(email: str, display_name: str) -> Optional[Dict]:
    """
    Создаёт пользователя в Jira через API
    
    Документация: https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-users/#api-rest-api-3-user-post
    """
    url = f"{JIRA_URL}/rest/api/3/user"
    
    auth = (ADMIN_EMAIL, API_TOKEN)
    
    payload = {
        "emailAddress": email,
        "displayName": display_name,
        "products": ["jira-software"]  # Даём доступ к Jira Software
    }
    
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, json=payload, auth=auth, headers=headers)
        
        if response.status_code == 201:
            user_data = response.json()
            print(f"   ✅ Создан: {display_name}")
            print(f"      Email: {email}")
            print(f"      AccountId: {user_data.get('accountId')}")
            return user_data
        elif response.status_code == 400:
            error_text = response.text.lower()
            if "already exists" in error_text or "user exists" in error_text:
                print(f"   ⚠️ Уже существует: {email}")
                return find_user_by_email(email)
            else:
                print(f"   ❌ Ошибка: {response.status_code}")
                print(f"      {response.text}")
                return None
        elif response.status_code == 403:
            print(f"   ❌ Нет прав: {response.status_code}")
            print("      Возможно, у вас недостаточно прав для создания пользователей")
            print("      Требуется роль администратора Jira")
            return None
        else:
            print(f"   ❌ Ошибка {response.status_code}: {email}")
            if response.text:
                print(f"      {response.text[:200]}")
            return None
            
    except requests.exceptions.ConnectionError as e:
        print(f"   ❌ Не удалось подключиться к Jira: {e}")
        print("      Проверьте JIRA_INSTANCE в config.py")
        return None
    except Exception as e:
        print(f"   ❌ Исключение: {e}")
        return None


def find_user_by_email(email: str) -> Optional[Dict]:
    """Ищет пользователя по email и возвращает его данные"""
    url = f"{JIRA_URL}/rest/api/3/user/search"
    auth = (ADMIN_EMAIL, API_TOKEN)
    params = {"query": email}
    
    try:
        response = requests.get(url, params=params, auth=auth, timeout=30)
        if response.status_code == 200:
            users = response.json()
            for user in users:
                if user.get('emailAddress') == email:
                    print(f"      Найден существующий: {user.get('accountId')}")
                    return user
        return None
    except Exception as e:
        print(f"   ⚠️ Ошибка поиска: {e}")
        return None


def add_user_to_group(account_id: str, group_name: str = "jira-software-users") -> bool:
    """
    Добавляет пользователя в группу (для доступа к проектам)
    """
    # Сначала проверим, существует ли группа
    group_search_url = f"{JIRA_URL}/rest/api/3/groups/picker"
    auth = (ADMIN_EMAIL, API_TOKEN)
    params = {"query": group_name}
    
    try:
        response = requests.get(group_search_url, params=params, auth=auth, timeout=30)
        if response.status_code == 200:
            groups = response.json().get('groups', [])
            if groups:
                group_id = groups[0].get('groupId')
                # Добавляем пользователя в группу
                add_url = f"{JIRA_URL}/rest/api/3/group/user"
                payload = {
                    "groupId": group_id,
                    "accountId": account_id
                }
                add_response = requests.post(add_url, json=payload, auth=auth, timeout=30)
                if add_response.status_code in [200, 201]:
                    print(f"      Добавлен в группу: {group_name}")
                    return True
                else:
                    print(f"      ⚠️ Не добавлен в группу (код {add_response.status_code})")
                    return False
            else:
                print(f"      ⚠️ Группа '{group_name}' не найдена")
                return False
        else:
            print(f"      ⚠️ Не удалось найти группу (код {response.status_code})")
            return False
    except Exception as e:
        print(f"      ⚠️ Ошибка добавления в группу: {e}")
        return False


def save_users_to_file(users: List[Dict], filename: str = 'scripts/.test_users.json'):
    """Сохраняет пользователей в файл для других скриптов"""
    # Убедимся, что директория существует
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=2, ensure_ascii=False)
    print(f"\n💾 Данные сохранены в {filename}")


def print_summary(users: List[Dict]):
    """Выводит сводку созданных пользователей"""
    print("\n" + "=" * 60)
    print("📊 ИТОГОВАЯ СВОДКА")
    print("=" * 60)
    
    by_role = {}
    for user in users:
        role = user.get('role', 'other')
        by_role[role] = by_role.get(role, 0) + 1
    
    print(f"\n👥 Всего пользователей: {len(users)}")
    print("\n📋 По ролям:")
    for role, count in by_role.items():
        role_names = {
            'team_lead': '👨‍💼 Тимлиды',
            'manager': '📊 Руководители',
            'developer': '💻 Разработчики',
            'qa': '🧪 Тестировщики'
        }
        print(f"   {role_names.get(role, role)}: {count}")
    
    print("\n📋 Список AccountId для использования в других скриптах:")
    print("-" * 60)
    for user in users:
        print(f"  {user['email']} → {user['account_id']}")


def main():
    print("=" * 60)
    print("🚀 ЭТАП 1: СОЗДАНИЕ ТЕСТОВЫХ ПОЛЬЗОВАТЕЛЕЙ В JIRA")
    print("=" * 60)
    print(f"\n📡 Jira URL: {JIRA_URL}")
    print(f"👥 Пользователей для создания: {len(TEST_USERS)}")
    print(f"👤 Администратор: {ADMIN_EMAIL}")
    print("-" * 60)
    
    # Проверка подключения к Jira
    print("\n🔍 Проверка подключения к Jira...")
    try:
        test_response = requests.get(f"{JIRA_URL}/rest/api/3/serverInfo", 
                                      auth=(ADMIN_EMAIL, API_TOKEN), 
                                      timeout=10)
        if test_response.status_code != 200:
            print(f"❌ Не удалось подключиться к Jira. Код: {test_response.status_code}")
            print("   Проверьте JIRA_INSTANCE, ADMIN_EMAIL и API_TOKEN в config.py")
            return
        print("✅ Подключение успешно")
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        return
    
    created_users = []
    failed_users = []
    
    for i, user in enumerate(TEST_USERS, 1):
        print(f"\n📝 [{i}/{len(TEST_USERS)}] {user['email']}")
        
        # Создаём пользователя
        jira_user = create_jira_user(user['email'], user['display_name'])
        
        if jira_user:
            account_id = jira_user.get('accountId')
            
            if account_id:
                # Добавляем в группу
                add_user_to_group(account_id)
                
                # Сохраняем информацию
                created_users.append({
                    "email": user['email'],
                    "display_name": user['display_name'],
                    "account_id": account_id,
                    "role": user.get('role', 'developer'),
                    "load_profile": user.get('load_profile', 'normal')
                })
            else:
                print(f"   ⚠️ Не удалось получить accountId")
                failed_users.append(user['email'])
        else:
            failed_users.append(user['email'])
        
        time.sleep(0.5)  # Пауза между запросами
    
    # Выводим результаты
    print("\n" + "=" * 60)
    print("📊 РЕЗУЛЬТАТЫ СОЗДАНИЯ ПОЛЬЗОВАТЕЛЕЙ")
    print("=" * 60)
    
    if created_users:
        print(f"\n✅ Успешно: {len(created_users)} пользователей")
        if failed_users:
            print(f"❌ Не удалось: {len(failed_users)} пользователей")
            for email in failed_users:
                print(f"   - {email}")
        
        print_summary(created_users)
        
        # Сохраняем в файл
        save_users_to_file(created_users)
        
    else:
        print("\n❌ Не удалось создать ни одного пользователя")
        print("\n🔍 Возможные причины:")
        print("   1. Неверный JIRA_INSTANCE в config.py")
        print("   2. Неверный ADMIN_EMAIL или API_TOKEN")
        print("   3. Недостаточно прав (нужна роль администратора)")
        print("   4. Проблемы с сетью или VPN")
    
    print("\n" + "=" * 60)
    if created_users:
        print("🎯 СЛЕДУЮЩИЙ ШАГ:")
        print("   Запустите: python scripts/02_create_test_projects.py")
    else:
        print("⚠️ Исправьте проблемы и запустите скрипт снова")
    print("=" * 60)


if __name__ == "__main__":
    main()