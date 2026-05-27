#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
create_health_issues_calculated.py

Создаёт задачи для проекта HEALTH с ПРЕДВАРИТЕЛЬНЫМ РАСЧЁТОМ.
Перед созданием показывает:
- Сколько задач будет создано
- Какое распределение статусов
- Ожидаемый WI после создания

Запуск: docker-compose exec backend python scripts/create_health_issues_calculated.py
"""

import requests
import sys
import os
import random
import json
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import JIRA_URL, ADMIN_EMAIL, API_TOKEN, MY_EMAIL


def print_info(msg: str): print(f"ℹ️ {msg}")
def print_success(msg: str): print(f"✅ {msg}")
def print_error(msg: str): print(f"❌ {msg}")
def print_warning(msg: str): print(f"⚠️ {msg}")


# Сотрудники HEALTH проекта
HEALTH_TEAM = {
    "team_lead": {"email": "anna.smirnova@test.com", "role": "team_lead", "target_open_sp": 8},
    "developers": [
        {"email": "alexey.ivanov@test.com", "role": "developer", "target_open_sp": 12},
        {"email": "elena.petrova@test.com", "role": "developer", "target_open_sp": 12},
        {"email": "mikhail.sidorov@test.com", "role": "developer", "target_open_sp": 12}
    ],
    "qa": [
        {"email": "pavel.sokolov@test.com", "role": "qa", "target_open_sp": 6},
        {"email": "natalia.lebedeva@test.com", "role": "qa", "target_open_sp": 6}
    ]
}

# Целевой WI для проекта
TARGET_WI = 0.85
WEEKS = 4

EMAIL_TO_ACCOUNT_ID = {}


def load_users():
    """Загружает пользователей из файла"""
    users_file = os.path.join(os.path.dirname(__file__), '.test_users.json')
    if not os.path.exists(users_file):
        print_error("Файл с пользователями не найден!")
        return False
    
    with open(users_file, 'r', encoding='utf-8') as f:
        users = json.load(f)
    
    for user in users:
        EMAIL_TO_ACCOUNT_ID[user['email']] = user['account_id']
    
    print_success(f"Загружено {len(EMAIL_TO_ACCOUNT_ID)} пользователей")
    return True


def calculate_required_closed_sp(open_sp: float, target_wi: float, weeks: int) -> float:
    """Рассчитывает необходимое количество закрытых SP для достижения целевого WI"""
    # WI = open_sp / (closed_sp / weeks) = (open_sp * weeks) / closed_sp
    # closed_sp = (open_sp * weeks) / target_wi
    return (open_sp * weeks) / target_wi


def calculate_expected_wi(open_sp: float, closed_sp: float, weeks: int) -> float:
    """Рассчитывает ожидаемый WI на основе открытых и закрытых SP"""
    if closed_sp == 0:
        return 999
    velocity = closed_sp / weeks
    return open_sp / velocity


def preview_plan():
    """Показывает план создания задач и ожидаемые результаты"""
    
    print("\n" + "=" * 70)
    print("📊 ПРЕДВАРИТЕЛЬНЫЙ РАСЧЁТ")
    print("=" * 70)
    
    total_open_sp = 0
    total_closed_sp_needed = 0
    all_members = []
    
    # Team Lead
    tl = HEALTH_TEAM["team_lead"]
    tl_open_sp = tl["target_open_sp"]
    tl_closed_needed = calculate_required_closed_sp(tl_open_sp, TARGET_WI, WEEKS)
    total_open_sp += tl_open_sp
    total_closed_sp_needed += tl_closed_needed
    all_members.append({
        "name": tl["email"].split('@')[0],
        "role": "Team Lead",
        "open_sp": tl_open_sp,
        "closed_needed": tl_closed_needed,
        "expected_wi": TARGET_WI
    })
    
    # Developers
    for dev in HEALTH_TEAM["developers"]:
        dev_open_sp = dev["target_open_sp"]
        dev_closed_needed = calculate_required_closed_sp(dev_open_sp, TARGET_WI, WEEKS)
        total_open_sp += dev_open_sp
        total_closed_sp_needed += dev_closed_needed
        all_members.append({
            "name": dev["email"].split('@')[0],
            "role": "Developer",
            "open_sp": dev_open_sp,
            "closed_needed": dev_closed_needed,
            "expected_wi": TARGET_WI
        })
    
    # QA
    for qa in HEALTH_TEAM["qa"]:
        qa_open_sp = qa["target_open_sp"]
        qa_closed_needed = calculate_required_closed_sp(qa_open_sp, TARGET_WI, WEEKS)
        total_open_sp += qa_open_sp
        total_closed_sp_needed += qa_closed_needed
        all_members.append({
            "name": qa["email"].split('@')[0],
            "role": "QA",
            "open_sp": qa_open_sp,
            "closed_needed": qa_closed_needed,
            "expected_wi": TARGET_WI
        })
    
    print("\n👥 ПО СОТРУДНИКАМ:")
    print(f"{'Сотрудник':<25} {'Роль':<12} {'Open SP':<10} {'Closed SP (4w)':<15} {'Ожидаемый WI':<12}")
    print("-" * 80)
    
    for m in all_members:
        print(f"{m['name']:<25} {m['role']:<12} {m['open_sp']:<10} {m['closed_needed']:<15.1f} {m['expected_wi']:<12}")
    
    print("-" * 80)
    print(f"{'ИТОГО:':<25} {'':<12} {total_open_sp:<10} {total_closed_sp_needed:<15.1f}")
    
    print("\n📊 РАСЧЁТ ОЖИДАЕМОГО WI (если добавим нужное количество закрытых задач):")
    expected_wi = calculate_expected_wi(total_open_sp, total_closed_sp_needed, WEEKS)
    print(f"   Total Open SP: {total_open_sp}")
    print(f"   Total Closed SP (4 weeks): {total_closed_sp_needed:.1f}")
    print(f"   Velocity: {total_closed_sp_needed / WEEKS:.2f} SP/неделю")
    print(f"   ** Ожидаемый WI: {expected_wi:.2f} **")
    
    status = "🟢 ОПТИМАЛЬНО" if 0.7 <= expected_wi <= 1.1 else ("🟡 ПОВЫШЕННАЯ" if expected_wi < 1.3 else "🔴 ПЕРЕГРУЗ")
    print(f"\n   Статус: {status}")
    
    return all_members, total_open_sp, total_closed_sp_needed


def calculate_issues_to_create(member_open_sp: float, member_closed_needed: float):
    """Рассчитывает количество задач для создания"""
    
    # Открытые задачи (SP 1-3)
    open_issues_count = max(4, int(member_open_sp / 2))
    open_sp_distribution = []
    remaining_sp = member_open_sp
    
    for i in range(open_issues_count - 1):
        sp = random.uniform(1, 3)
        sp = round(min(sp, remaining_sp - 0.5), 1)
        open_sp_distribution.append(sp)
        remaining_sp -= sp
    
    open_sp_distribution.append(round(remaining_sp, 1))
    
    # Закрытые задачи (SP 2-5)
    closed_issues_count = max(3, int(member_closed_needed / 3))
    closed_sp_distribution = []
    remaining_sp = member_closed_needed
    
    for i in range(closed_issues_count - 1):
        sp = random.uniform(2, 5)
        sp = round(min(sp, remaining_sp - 1), 1)
        closed_sp_distribution.append(sp)
        remaining_sp -= sp
    
    closed_sp_distribution.append(round(remaining_sp, 1))
    
    return {
        "open_issues": open_issues_count,
        "open_sp_list": open_sp_distribution,
        "closed_issues": closed_issues_count,
        "closed_sp_list": closed_sp_distribution
    }


def create_issue(project_key: str, summary: str, assignee_id: str, story_points: float, status: str) -> bool:
    """Создаёт задачу в Jira с указанным статусом"""
    
    auth = (ADMIN_EMAIL, API_TOKEN)
    
    # Сначала создаём задачу
    payload = {
        "fields": {
            "project": {"key": project_key},
            "summary": summary,
            "issuetype": {"name": "Task"},
            "priority": {"name": "Medium"},
            "assignee": {"accountId": assignee_id},
            "customfield_10016": story_points
        }
    }
    
    try:
        resp = requests.post(f"{JIRA_URL}/rest/api/3/issue", 
                            json=payload, auth=auth,
                            headers={"Content-Type": "application/json"}, timeout=60)
        
        if resp.status_code != 201:
            return False
        
        issue_key = resp.json().get('key')
        
        # Если нужен статус "В работе" или "Готово" — выполняем переходы
        if status != "К выполнению":
            # Получаем переходы
            transitions_resp = requests.get(
                f"{JIRA_URL}/rest/api/3/issue/{issue_key}/transitions",
                auth=auth, timeout=30
            )
            
            if transitions_resp.status_code == 200:
                transitions = transitions_resp.json().get('transitions', [])
                
                in_progress_id = None
                done_id = None
                
                for t in transitions:
                    to_name = t.get('to', {}).get('name')
                    if to_name == "В работе":
                        in_progress_id = t.get('id')
                    elif to_name == "Готово":
                        done_id = t.get('id')
                
                if status == "В работе" and in_progress_id:
                    requests.post(
                        f"{JIRA_URL}/rest/api/3/issue/{issue_key}/transitions",
                        json={"transition": {"id": in_progress_id}}, auth=auth
                    )
                elif status == "Готово":
                    if in_progress_id:
                        requests.post(
                            f"{JIRA_URL}/rest/api/3/issue/{issue_key}/transitions",
                            json={"transition": {"id": in_progress_id}}, auth=auth
                        )
                    if done_id:
                        requests.post(
                            f"{JIRA_URL}/rest/api/3/issue/{issue_key}/transitions",
                            json={"transition": {"id": done_id}}, auth=auth
                        )
        
        print(f"   ✅ {issue_key}: SP={story_points}, статус={status}")
        return True
        
    except Exception as e:
        print_error(f"  Ошибка: {e}")
        return False


def main():
    print("=" * 70)
    print("СОЗДАНИЕ ЗАДАЧ ДЛЯ HEALTH С ПРЕДВАРИТЕЛЬНЫМ РАСЧЁТОМ")
    print("=" * 70)
    
    if not load_users():
        return
    
    # Показываем предварительный расчёт
    members, total_open_sp, total_closed_needed = preview_plan()
    
    # Спрашиваем подтверждение
    print("\n" + "=" * 70)
    response = input("❓ СОЗДАТЬ ЗАДАЧИ с такими параметрами? (y/n): ")
    
    if response.lower() != 'y':
        print("❌ Операция отменена")
        return
    
    # Проверяем подключение к Jira
    try:
        resp = requests.get(f"{JIRA_URL}/rest/api/3/serverInfo", 
                           auth=(ADMIN_EMAIL, API_TOKEN), timeout=30)
        if resp.status_code != 200:
            print_error("Ошибка подключения к Jira")
            return
        print_success("Подключено к Jira")
    except Exception as e:
        print_error(f"Ошибка: {e}")
        return
    
    # Удаляем старые задачи HEALTH
    print("\n🔍 Удаление старых задач HEALTH...")
    auth = (ADMIN_EMAIL, API_TOKEN)
    response = requests.get(
        f"{JIRA_URL}/rest/api/3/search",
        auth=auth,
        params={"jql": "project=HEALTH", "maxResults": 200},
        timeout=30
    )
    
    if response.status_code == 200:
        issues = response.json().get("issues", [])
        print(f"   Найдено задач: {len(issues)}")
        
        for issue in issues:
            issue_key = issue["key"]
            resp = requests.delete(f"{JIRA_URL}/rest/api/3/issue/{issue_key}", auth=auth)
            if resp.status_code == 204:
                print(f"   ✅ Удалена {issue_key}")
    
    # Создаём задачи
    print("\n📝 СОЗДАНИЕ НОВЫХ ЗАДАЧ")
    print("-" * 70)
    
    total_created = 0
    
    # Team Lead
    tl = HEALTH_TEAM["team_lead"]
    assignee_id = EMAIL_TO_ACCOUNT_ID.get(tl["email"])
    if assignee_id:
        print(f"\n👨‍💼 Team Lead: {tl['email']}")
        plan = calculate_issues_to_create(tl["target_open_sp"], calculate_required_closed_sp(tl["target_open_sp"], TARGET_WI, WEEKS))
        
        # Открытые задачи (статус "К выполнению" или "В работе")
        for i, sp in enumerate(plan["open_sp_list"]):
            status = "К выполнению" if i % 3 != 0 else "В работе"
            create_issue("HEALTH", f"Задача {i+1}", assignee_id, sp, status)
            total_created += 1
        
        # Закрытые задачи (статус "Готово")
        for i, sp in enumerate(plan["closed_sp_list"]):
            create_issue("HEALTH", f"Закрытая задача {i+1}", assignee_id, sp, "Готово")
            total_created += 1
    
    # Developers
    print(f"\n💻 Developers:")
    for dev in HEALTH_TEAM["developers"]:
        assignee_id = EMAIL_TO_ACCOUNT_ID.get(dev["email"])
        if assignee_id:
            print(f"   {dev['email']}")
            plan = calculate_issues_to_create(dev["target_open_sp"], calculate_required_closed_sp(dev["target_open_sp"], TARGET_WI, WEEKS))
            
            for i, sp in enumerate(plan["open_sp_list"]):
                status = "К выполнению" if i % 3 != 0 else "В работе"
                create_issue("HEALTH", f"Задача {i+1}", assignee_id, sp, status)
                total_created += 1
            
            for i, sp in enumerate(plan["closed_sp_list"]):
                create_issue("HEALTH", f"Закрытая задача {i+1}", assignee_id, sp, "Готово")
                total_created += 1
    
    # QA
    print(f"\n🧪 QA:")
    for qa in HEALTH_TEAM["qa"]:
        assignee_id = EMAIL_TO_ACCOUNT_ID.get(qa["email"])
        if assignee_id:
            print(f"   {qa['email']}")
            plan = calculate_issues_to_create(qa["target_open_sp"], calculate_required_closed_sp(qa["target_open_sp"], TARGET_WI, WEEKS))
            
            for i, sp in enumerate(plan["open_sp_list"]):
                status = "К выполнению" if i % 3 != 0 else "В работе"
                create_issue("HEALTH", f"Задача {i+1}", assignee_id, sp, status)
                total_created += 1
            
            for i, sp in enumerate(plan["closed_sp_list"]):
                create_issue("HEALTH", f"Закрытая задача {i+1}", assignee_id, sp, "Готово")
                total_created += 1
    
    print("\n" + "=" * 70)
    print_success(f"СОЗДАНО ВСЕГО ЗАДАЧ: {total_created}")
    print("=" * 70)
    
    print("\n📊 СЛЕДУЮЩИЕ ШАГИ:")
    print("1. Синхронизируйте HEALTH в БД:")
    print("   curl -X POST 'http://localhost:8000/jira/sync/HEALTH?instance_name=newsitealf&sync_statuses_first=true' -H 'Cookie: session_token=YOUR_TOKEN'")
    print("\n2. Обновите даты:")
    print("   docker-compose exec backend python scripts/update_health_dates.py")
    print("\n3. Проверьте Workload Index:")
    print("   curl 'http://localhost:8000/metrics/workload/HEALTH?weeks=4' | python -m json.tool")


if __name__ == "__main__":
    main()