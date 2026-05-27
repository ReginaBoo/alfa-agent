# backend/scripts/create_test_data_in_db.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Создание ТЕСТОВЫХ данных в БД для HEALTH (без создания в Jira)
Запуск: docker-compose exec backend python scripts/create_test_data_in_db.py
"""

import sys
import os
import random
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.session import SessionLocal
from sqlalchemy import text

# Конфигурация HEALTH проекта
HEALTH_TEAM = {
    "team_lead": {
        "email": "anna.smirnova@test.com",
        "account_id": "712020:7a8d0a68-b649-4223-993c-8f40259aba04",
        "target_open_sp": 8,
        "target_closed_sp": 38
    },
    "developers": [
        {"email": "alexey.ivanov@test.com", "account_id": "712020:dc664c11-879e-4276-a1f2-ce3cc508e875", "target_open_sp": 12, "target_closed_sp": 56},
        {"email": "elena.petrova@test.com", "account_id": "712020:ce4636a9-8a8a-4755-bed2-dd71f7dc501c", "target_open_sp": 12, "target_closed_sp": 56},
        {"email": "mikhail.sidorov@test.com", "account_id": "712020:c9c5639a-029c-4516-b211-5bfadebb550d", "target_open_sp": 12, "target_closed_sp": 56}
    ],
    "qa": [
        {"email": "pavel.sokolov@test.com", "account_id": "712020:0428a807-0aef-4b7d-b1cc-3fde971a5e1c", "target_open_sp": 6, "target_closed_sp": 28},
        {"email": "natalia.lebedeva@test.com", "account_id": "712020:2e7a65d1-6289-4b72-b480-f562838868e5", "target_open_sp": 6, "target_closed_sp": 28}
    ]
}

def get_token_id():
    """Получает integration_token_id для пользователя test.jira.test@yandex.ru"""
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT t.id 
            FROM identity.integration_tokens t
            JOIN identity.users u ON u.id = t.user_id
            WHERE u.email = 'test.jira.test@yandex.ru'
            LIMIT 1
        """)).fetchone()
        return result[0] if result else None
    finally:
        db.close()

def clear_health_data(db):
    """Очищает существующие данные HEALTH"""
    db.execute(text("DELETE FROM normalized.jira_issues WHERE project_key = 'HEALTH'"))
    print("   ✅ Очищены старые задачи HEALTH")

def generate_open_tasks(account_id, total_sp, prefix):
    """Генерирует открытые задачи (В работе, К выполнению)"""
    tasks = []
    count = max(3, int(total_sp / 2))
    sp_list = []
    remaining = total_sp
    
    for i in range(count - 1):
        sp = round(random.uniform(1, 3), 1)
        sp = min(sp, remaining - 0.5)
        sp_list.append(sp)
        remaining -= sp
    sp_list.append(round(remaining, 1))
    
    for i, sp in enumerate(sp_list):
        status = random.choice(["В работе", "К выполнению"])
        days_ago = random.randint(1, 10)
        tasks.append({
            "issue_key": f"HEALTH-{prefix}-{i+1}",
            "summary": f"Задача {i+1}",
            "status": status,
            "story_points": sp,
            "issue_type": "Task",
            "assignee_account_id": account_id,
            "created_at": datetime.now() - timedelta(days=days_ago),
            "updated_at": datetime.now()
        })
    return tasks

def generate_closed_tasks(account_id, total_sp, prefix):
    """Генерирует закрытые задачи (Готово)"""
    tasks = []
    count = max(3, int(total_sp / 3))
    sp_list = []
    remaining = total_sp
    
    for i in range(count - 1):
        sp = round(random.uniform(2, 5), 1)
        sp = min(sp, remaining - 1)
        sp_list.append(sp)
        remaining -= sp
    sp_list.append(round(remaining, 1))
    
    for i, sp in enumerate(sp_list):
        created_days = random.randint(15, 30)
        closed_days = random.randint(3, 10)
        tasks.append({
            "issue_key": f"HEALTH-{prefix}-{i+1}",
            "summary": f"Завершенная задача {i+1}",
            "status": "Готово",
            "story_points": sp,
            "issue_type": "Task",
            "assignee_account_id": account_id,
            "created_at": datetime.now() - timedelta(days=created_days),
            "updated_at": datetime.now() - timedelta(days=closed_days)
        })
    return tasks

def main():
    print("=" * 70)
    print("📝 СОЗДАНИЕ ТЕСТОВЫХ ДАННЫХ В БД ДЛЯ HEALTH")
    print("=" * 70)
    
    # Получаем token_id
    token_id = get_token_id()
    if not token_id:
        print("❌ Не найден токен для пользователя test.jira.test@yandex.ru")
        print("   Сначала авторизуйтесь в браузере: http://localhost:8000/auth/login")
        return
    
    print(f"✅ Найден token_id: {token_id}")
    
    db = SessionLocal()
    
    try:
        # Очищаем старые данные
        print("\n🗑️ Очистка старых данных...")
        clear_health_data(db)
        
        all_tasks = []
        
        # Team Lead
        print("\n👨‍💼 Team Lead (Анна Смирнова)")
        tl = HEALTH_TEAM["team_lead"]
        open_tasks = generate_open_tasks(tl["account_id"], tl["target_open_sp"], "TL")
        closed_tasks = generate_closed_tasks(tl["account_id"], tl["target_closed_sp"], "TL-DONE")
        all_tasks.extend(open_tasks)
        all_tasks.extend(closed_tasks)
        print(f"   Открытых: {len(open_tasks)} (SP: {tl['target_open_sp']})")
        print(f"   Закрытых: {len(closed_tasks)} (SP: {tl['target_closed_sp']})")
        
        # Developers
        print("\n💻 Developers:")
        for i, dev in enumerate(HEALTH_TEAM["developers"], 1):
            open_tasks = generate_open_tasks(dev["account_id"], dev["target_open_sp"], f"DEV{i}")
            closed_tasks = generate_closed_tasks(dev["account_id"], dev["target_closed_sp"], f"DEV{i}-DONE")
            all_tasks.extend(open_tasks)
            all_tasks.extend(closed_tasks)
            print(f"   {dev['email']}: открытых {len(open_tasks)}, закрытых {len(closed_tasks)}")
        
        # QA
        print("\n🧪 QA:")
        for i, qa in enumerate(HEALTH_TEAM["qa"], 1):
            open_tasks = generate_open_tasks(qa["account_id"], qa["target_open_sp"], f"QA{i}")
            closed_tasks = generate_closed_tasks(qa["account_id"], qa["target_closed_sp"], f"QA{i}-DONE")
            all_tasks.extend(open_tasks)
            all_tasks.extend(closed_tasks)
            print(f"   {qa['email']}: открытых {len(open_tasks)}, закрытых {len(closed_tasks)}")
        
        # Вставляем задачи в БД
        print(f"\n💾 Вставка {len(all_tasks)} задач в БД...")
        
        for task in all_tasks:
            db.execute(text("""
                INSERT INTO normalized.jira_issues (
                    issue_key, project_key, summary, status, issue_type,
                    assignee_account_id, story_points, created_at, updated_at,
                    project_integration_id
                ) VALUES (
                    :issue_key, 'HEALTH', :summary, :status, :issue_type,
                    :assignee_account_id, :story_points, :created_at, :updated_at,
                    :token_id
                )
            """), {
                "issue_key": task["issue_key"],
                "summary": task["summary"],
                "status": task["status"],
                "issue_type": task["issue_type"],
                "assignee_account_id": task["assignee_account_id"],
                "story_points": task["story_points"],
                "created_at": task["created_at"],
                "updated_at": task["updated_at"],
                "token_id": token_id
            })
        
        db.commit()
        
        # Показываем статистику
        print("\n" + "=" * 70)
        print("📊 СТАТИСТИКА СОЗДАННЫХ ЗАДАЧ")
        print("=" * 70)
        
        result = db.execute(text("""
            SELECT 
                status,
                COUNT(*) as count,
                SUM(story_points) as total_sp,
                COUNT(DISTINCT assignee_account_id) as assignees
            FROM normalized.jira_issues
            WHERE project_key = 'HEALTH'
            GROUP BY status
            ORDER BY 
                CASE status 
                    WHEN 'В работе' THEN 1
                    WHEN 'К выполнению' THEN 2
                    WHEN 'Готово' THEN 3
                END
        """)).fetchall()
        
        for row in result:
            print(f"   {row[0]}: {row[1]} задач, {row[2]:.1f} SP, {row[3]} исполнителей")
        
        # Проверяем назначенных ответственных
        print("\n👥 НАЗНАЧЕННЫЕ ОТВЕТСТВЕННЫЕ:")
        result = db.execute(text("""
            SELECT 
                assignee_account_id,
                COUNT(*) as tasks_count
            FROM normalized.jira_issues
            WHERE project_key = 'HEALTH'
            GROUP BY assignee_account_id
            ORDER BY tasks_count DESC
        """)).fetchall()
        
        for row in result:
            print(f"   {row[0]}: {row[1]} задач")
        
        # Проверяем привязку к пользователю
        result = db.execute(text("""
            SELECT u.email, COUNT(i.issue_key) as issues
            FROM normalized.jira_issues i
            JOIN identity.integration_tokens t ON t.id = i.project_integration_id
            JOIN identity.users u ON u.id = t.user_id
            WHERE i.project_key = 'HEALTH'
            GROUP BY u.email
        """)).fetchall()
        
        print("\n🔗 Привязка к пользователям в БД:")
        for row in result:
            print(f"   {row[0]}: {row[1]} задач")
        
        print("\n" + "=" * 70)
        print("✅ ТЕСТОВЫЕ ДАННЫЕ УСПЕШНО СОЗДАНЫ!")
        print("=" * 70)
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()