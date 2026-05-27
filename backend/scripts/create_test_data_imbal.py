# backend/scripts/create_test_data_imbal.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Создание ТЕСТОВЫХ данных в БД для IMBAL (желтый статус, WI ~0.95)
Запуск: docker-compose exec backend python scripts/create_test_data_imbal.py
"""

import os
import sys
import random
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.session import SessionLocal
from sqlalchemy import text

IMBAL_TEAM = {
    "developers": [
        {"name": "Сергей Новиков", "email": "sergey.novikov@test.com", 
         "account_id": "712020:7aa3e311-dc3c-4852-b7af-ac1856bb83fb", "load": "overloaded"},
        {"name": "Татьяна Кузьмина", "email": "tatyana.kuzmina@test.com", 
         "account_id": "712020:18325838-7c5f-4ffa-8e21-375f59a6c604", "load": "underloaded"}
    ],
    "qa": [
        {"name": "Наталья Лебедева", "email": "natalia.lebedeva@test.com",
         "account_id": "712020:2e7a65d1-6289-4b72-b480-f562838868e5", "load": "normal"}
    ]
}

def get_token_id():
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT t.id FROM identity.integration_tokens t
            JOIN identity.users u ON u.id = t.user_id
            WHERE u.email = 'test.jira.test@yandex.ru' LIMIT 1
        """)).fetchone()
        return result[0] if result else None
    finally:
        db.close()

def generate_imbal_tasks(account_id, name, load_profile, token_id):
    """Генерирует задачи для желтого статуса (WI 86-100%)"""
    tasks = []
    
    if load_profile == "overloaded":
        # Для WI = 0.95 (95%) нужно: open_sp = 19, closed_sp = 80
        # velocity = 80/4 = 20, WI = 19/20 = 0.95
        open_sp = 19
        closed_sp_total = 80
        open_tasks_count = 6
        closed_tasks_count = 16
        sp_range_open = (2, 5)
        sp_range_closed = (3, 7)
        
    elif load_profile == "underloaded":
        # WI = 0.5 (зеленый)
        open_sp = 6
        closed_sp_total = 48
        open_tasks_count = 3
        closed_tasks_count = 12
        sp_range_open = (1, 3)
        sp_range_closed = (3, 5)
        
    else:  # normal
        # WI = 0.85 (зеленый)
        open_sp = 11
        closed_sp_total = 52
        open_tasks_count = 4
        closed_tasks_count = 12
        sp_range_open = (2, 4)
        sp_range_closed = (3, 6)
    
    # ===== ОТКРЫТЫЕ ЗАДАЧИ =====
    remaining_open = open_sp
    for i in range(open_tasks_count):
        if i == open_tasks_count - 1:
            sp = round(remaining_open, 1)
        else:
            sp = round(random.uniform(sp_range_open[0], sp_range_open[1]), 1)
            sp = min(sp, remaining_open - 0.5)
            remaining_open -= sp
        
        status = random.choice(["В работе", "К выполнению"])
        days_ago = random.randint(1, 10)
        
        tasks.append({
            "issue_key": f"IMBAL-{name[:3]}-O{i+1}",
            "summary": f"{name}: Задача {i+1}",
            "status": status,
            "story_points": sp,
            "issue_type": "Task",
            "assignee_account_id": account_id,
            "created_at": datetime.now() - timedelta(days=days_ago),
            "updated_at": datetime.now(),
            "token_id": token_id
        })
    
    # ===== ЗАКРЫТЫЕ ЗАДАЧИ =====
    remaining_closed = closed_sp_total
    for i in range(closed_tasks_count):
        if i == closed_tasks_count - 1:
            sp = round(remaining_closed, 1)
        else:
            sp = round(random.uniform(sp_range_closed[0], sp_range_closed[1]), 1)
            sp = min(sp, remaining_closed - 1)
            remaining_closed -= sp
        
        week_offset = random.randint(0, 3)
        days_ago_closed = week_offset * 7 + random.randint(1, 6)
        days_ago_created = days_ago_closed + random.randint(5, 20)
        
        tasks.append({
            "issue_key": f"IMBAL-{name[:3]}-C{i+1}",
            "summary": f"{name}: Завершено {i+1}",
            "status": "Готово",
            "story_points": sp,
            "issue_type": "Task",
            "assignee_account_id": account_id,
            "created_at": datetime.now() - timedelta(days=days_ago_created),
            "updated_at": datetime.now() - timedelta(days=days_ago_closed),
            "token_id": token_id
        })
    
    return tasks

def main():
    print("=" * 70)
    print("📝 СОЗДАНИЕ ДАННЫХ ДЛЯ IMBAL (ЖЕЛТЫЙ СТАТУС, WI ~0.95)")
    print("=" * 70)
    
    token_id = get_token_id()
    if not token_id:
        print("❌ Токен не найден!")
        return
    
    print(f"✅ Token ID: {token_id}")
    
    db = SessionLocal()
    
    try:
        # Очищаем старые данные
        print("\n🗑️ Очистка старых задач IMBAL...")
        deleted = db.execute(text("DELETE FROM normalized.jira_issues WHERE project_key = 'IMBAL'"))
        db.commit()
        print(f"   Удалено задач: {deleted.rowcount}")
        
        all_tasks = []
        
        print("\n👥 Генерация задач (желтый статус):")
        for dev in IMBAL_TEAM["developers"]:
            tasks = generate_imbal_tasks(dev["account_id"], dev["name"], dev["load"], token_id)
            all_tasks.extend(tasks)
            print(f"   {dev['name']} ({dev['load']}): {len(tasks)} задач")
        
        for qa in IMBAL_TEAM["qa"]:
            tasks = generate_imbal_tasks(qa["account_id"], qa["name"], qa["load"], token_id)
            all_tasks.extend(tasks)
            print(f"   {qa['name']} ({qa['load']}): {len(tasks)} задач")
        
        # Вставка в БД
        print(f"\n💾 Вставка {len(all_tasks)} задач...")
        
        for task in all_tasks:
            db.execute(text("""
                INSERT INTO normalized.jira_issues (
                    issue_key, project_key, summary, status, issue_type,
                    assignee_account_id, story_points, created_at, updated_at,
                    project_integration_id, is_deleted
                ) VALUES (
                    :issue_key, 'IMBAL', :summary, :status, :issue_type,
                    :assignee_account_id, :story_points, :created_at, :updated_at,
                    :token_id, false
                )
            """), task)
        
        db.commit()
        
        # Статистика
        print("\n" + "=" * 70)
        print("📊 СТАТИСТИКА IMBAL")
        print("=" * 70)
        
        result = db.execute(text("""
            SELECT 
                SUM(CASE WHEN status IN ('В работе', 'К выполнению') THEN story_points ELSE 0 END) as open_sp,
                SUM(CASE WHEN status = 'Готово' AND updated_at > NOW() - INTERVAL '28 days' THEN story_points ELSE 0 END) as closed_sp_4weeks
            FROM normalized.jira_issues
            WHERE project_key = 'IMBAL'
        """)).fetchone()
        
        if result:
            open_sp = result[0] or 0
            closed_sp = result[1] or 0
            velocity = closed_sp / 4 if closed_sp > 0 else 1
            wi = open_sp / velocity if velocity > 0 else 0
            wi_percent = int(wi * 100)
            
            print(f"\n📈 Workload Index: {wi_percent} ({wi:.2f})")
            
            if 86 <= wi_percent <= 100:
                print("   ✅ Желтый статус (WI 86-100%)")
            else:
                print(f"   ⚠️ Ожидался желтый (86-100%), получен {wi_percent}%")
        
        print("\n✅ Данные для IMBAL созданы!")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()