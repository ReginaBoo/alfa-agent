# backend/scripts/create_test_data_crunch_fixed.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Создание ТЕСТОВЫХ данных в БД для CRUNCH (WI = 1.4-1.8)
Запуск: docker-compose exec backend python scripts/create_test_data_crunch_fixed.py
"""

import os
import sys
import random
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.session import SessionLocal
from sqlalchemy import text

CRUNCH_TEAM = {
    "developers": [
        {"name": "Максим Васильев", "email": "maxim.vasiliev@test.com", 
         "account_id": "712020:4fcc4944-7521-46fb-a4a3-e3c4795eb856", "load": "overloaded"},
        {"name": "Ирина Морозова", "email": "irina.morozova@test.com", 
         "account_id": "712020:fca64fca-b519-408f-97b2-6beef2c0b4b5", "load": "overloaded"},
        {"name": "Андрей Соколов", "email": "andrey.sokolov@test.com", 
         "account_id": "712020:f3ba1b08-7826-4a70-bb44-0358f89b4952", "load": "normal"}
    ],
    "qa": [
        {"name": "Мария Виноградова", "email": "maria.vinogradova@test.com",
         "account_id": "712020:e00a96ff-008a-403f-bbd6-edb96280176e", "load": "overloaded"}
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

def generate_crunch_tasks(account_id, name, load_profile, token_id):
    """Генерирует задачи для правильного WI (1.4-1.8)"""
    tasks = []
    
    if load_profile == "overloaded":
        # Чтобы WI = 1.6:
        # open_weight = 16 SP
        # velocity = 10 SP/неделя → 40 SP за 4 недели
        open_sp = 16
        closed_sp_total = 40
        open_tasks_count = 6      # Меньше задач, но с бОльшими SP
        closed_tasks_count = 8    # Больше закрытых задач
    else:
        # Чтобы WI = 0.9:
        open_sp = 10
        closed_sp_total = 44      # 11 SP в неделю
        open_tasks_count = 4
        closed_tasks_count = 10
    
    # ===== ОТКРЫТЫЕ ЗАДАЧИ (status: "В работе" или "К выполнению") =====
    remaining_open = open_sp
    for i in range(open_tasks_count):
        if i == open_tasks_count - 1:
            sp = round(remaining_open, 1)
        else:
            # SP от 2 до 5 для перегруженных, от 1 до 3 для нормальных
            if load_profile == "overloaded":
                sp = round(random.uniform(2, 5), 1)
            else:
                sp = round(random.uniform(1, 3), 1)
            sp = min(sp, remaining_open - 0.5)
            remaining_open -= sp
        
        status = random.choice(["В работе", "К выполнению"])
        days_ago = random.randint(1, 14)
        
        tasks.append({
            "issue_key": f"CRUNCH-{name[:3]}-O{i+1}",
            "summary": f"{name}: Задача {i+1}",
            "status": status,
            "story_points": sp,
            "issue_type": "Task",  # Важно: Task имеет вес 3
            "assignee_account_id": account_id,
            "created_at": datetime.now() - timedelta(days=days_ago),
            "updated_at": datetime.now(),
            "token_id": token_id
        })
    
    # ===== ЗАКРЫТЫЕ ЗАДАЧИ (status: "Готово") - распределены по 4 неделям =====
    remaining_closed = closed_sp_total
    for i in range(closed_tasks_count):
        if i == closed_tasks_count - 1:
            sp = round(remaining_closed, 1)
        else:
            sp = round(random.uniform(3, 8), 1)  # Крупные закрытые задачи
            sp = min(sp, remaining_closed - 1)
            remaining_closed -= sp
        
        # Распределяем закрытия по последним 4 неделям
        week_offset = random.randint(0, 3)  # 0 = эта неделя, 3 = 4 недели назад
        days_ago_closed = week_offset * 7 + random.randint(1, 6)
        days_ago_created = days_ago_closed + random.randint(5, 20)
        
        tasks.append({
            "issue_key": f"CRUNCH-{name[:3]}-C{i+1}",
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
    print("📝 СОЗДАНИЕ ДАННЫХ ДЛЯ CRUNCH (WI = 1.4-1.8)")
    print("=" * 70)
    
    token_id = get_token_id()
    if not token_id:
        print("❌ Токен не найден! Сначала авторизуйтесь в браузере")
        return
    
    print(f"✅ Token ID: {token_id}")
    
    db = SessionLocal()
    
    try:
        # Очищаем старые данные
        print("\n🗑️ Очистка старых задач CRUNCH...")
        deleted = db.execute(text("DELETE FROM normalized.jira_issues WHERE project_key = 'CRUNCH'"))
        db.commit()
        print(f"   Удалено задач: {deleted.rowcount}")
        
        all_tasks = []
        
        print("\n👥 Генерация задач:")
        for dev in CRUNCH_TEAM["developers"]:
            tasks = generate_crunch_tasks(dev["account_id"], dev["name"], dev["load"], token_id)
            all_tasks.extend(tasks)
            print(f"   {dev['name']} ({dev['load']}): {len(tasks)} задач")
        
        for qa in CRUNCH_TEAM["qa"]:
            tasks = generate_crunch_tasks(qa["account_id"], qa["name"], qa["load"], token_id)
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
                    :issue_key, 'CRUNCH', :summary, :status, :issue_type,
                    :assignee_account_id, :story_points, :created_at, :updated_at,
                    :token_id, false
                )
            """), task)
        
        db.commit()
        
        # Подробная статистика
        print("\n" + "=" * 70)
        print("📊 СТАТИСТИКА CRUNCH")
        print("=" * 70)
        
        # Статусы
        result = db.execute(text("""
            SELECT status, COUNT(*) as cnt, SUM(story_points) as total_sp
            FROM normalized.jira_issues WHERE project_key = 'CRUNCH'
            GROUP BY status
        """)).fetchall()
        
        print("\nПо статусам:")
        for row in result:
            print(f"   {row[0]}: {row[1]} задач, {row[2]:.1f} SP")
        
        # По сотрудникам
        result = db.execute(text("""
            SELECT 
                CASE 
                    WHEN assignee_account_id = '712020:4fcc4944-7521-46fb-a4a3-e3c4795eb856' THEN 'Максим'
                    WHEN assignee_account_id = '712020:fca64fca-b519-408f-97b2-6beef2c0b4b5' THEN 'Ирина'
                    WHEN assignee_account_id = '712020:f3ba1b08-7826-4a70-bb44-0358f89b4952' THEN 'Андрей'
                    WHEN assignee_account_id = '712020:e00a96ff-008a-403f-bbd6-edb96280176e' THEN 'Мария'
                    ELSE assignee_account_id
                END as name,
                COUNT(*) as tasks,
                SUM(story_points) as total_sp
            FROM normalized.jira_issues
            WHERE project_key = 'CRUNCH'
            GROUP BY assignee_account_id
            ORDER BY total_sp DESC
        """)).fetchall()
        
        print("\nПо сотрудникам:")
        for row in result:
            print(f"   {row[0]}: {row[1]} задач, {row[2]:.1f} SP")
        
        # Расчет ожидаемого WI
        result = db.execute(text("""
            SELECT 
                SUM(CASE WHEN status IN ('В работе', 'К выполнению') THEN story_points ELSE 0 END) as open_sp,
                SUM(CASE WHEN status = 'Готово' AND updated_at > NOW() - INTERVAL '28 days' THEN story_points ELSE 0 END) as closed_sp_4weeks
            FROM normalized.jira_issues
            WHERE project_key = 'CRUNCH'
        """)).fetchone()
        
        if result:
            open_sp = result[0] or 0
            closed_sp_4weeks = result[1] or 0
            velocity = closed_sp_4weeks / 4 if closed_sp_4weeks > 0 else 1
            expected_wi = open_sp / velocity if velocity > 0 else 0
            
            print(f"\n📈 Ожидаемый WI: {expected_wi:.2f}")
            if 1.4 <= expected_wi <= 1.8:
                print("   ✅ Цель достигнута!")
            elif expected_wi > 1.8:
                print("   ⚠️ WI выше целевого (>1.8)")
            else:
                print("   ⚠️ WI ниже целевого (<1.4)")
        
        print("\n✅ Данные для CRUNCH созданы!")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()