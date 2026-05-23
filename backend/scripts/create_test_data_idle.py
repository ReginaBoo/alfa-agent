# backend/scripts/create_test_data_idle.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Создание ТЕСТОВЫХ данных в БД для IDLE (недогруженный проект)
Запуск: docker-compose exec backend python scripts/create_test_data_idle.py
"""

import os
import sys
import random
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.session import SessionLocal
from sqlalchemy import text

# Команда IDLE (из PROJECT_ASSIGNEES)
IDLE_TEAM = {
    "developers": [
        {"name": "Сергей Новиков", "email": "sergey.novikov@test.com", 
         "account_id": "712020:7aa3e311-dc3c-4852-b7af-ac1856bb83fb"}
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

def generate_idle_tasks(account_id, name, token_id):
    """Генерирует задачи для недогруженного проекта (WI < 0.7)"""
    tasks = []
    
    # Чтобы WI = 0.6:
    # open_sp = 8
    # closed_sp_4weeks = 54 (velocity = 13.5) → WI = 8 / 13.5 = 0.59
    open_sp = 8
    closed_sp_total = 54
    open_tasks_count = 4
    closed_tasks_count = 12
    
    # ===== ОТКРЫТЫЕ ЗАДАЧИ =====
    remaining_open = open_sp
    for i in range(open_tasks_count):
        if i == open_tasks_count - 1:
            sp = round(remaining_open, 1)
        else:
            sp = round(random.uniform(1, 3), 1)
            sp = min(sp, remaining_open - 0.5)
            remaining_open -= sp
        
        status = random.choice(["В работе", "К выполнению"])
        days_ago = random.randint(1, 10)
        
        tasks.append({
            "issue_key": f"IDLE-{i+1}",
            "summary": f"{name}: Задача {i+1}",
            "status": status,
            "story_points": sp,
            "issue_type": "Task",
            "assignee_account_id": account_id,
            "created_at": datetime.now() - timedelta(days=days_ago),
            "updated_at": datetime.now(),
            "token_id": token_id
        })
    
    # ===== ЗАКРЫТЫЕ ЗАДАЧИ (много, распределены по 4 неделям) =====
    remaining_closed = closed_sp_total
    for i in range(closed_tasks_count):
        if i == closed_tasks_count - 1:
            sp = round(remaining_closed, 1)
        else:
            sp = round(random.uniform(3, 6), 1)
            sp = min(sp, remaining_closed - 1)
            remaining_closed -= sp
        
        week_offset = random.randint(0, 3)
        days_ago_closed = week_offset * 7 + random.randint(1, 6)
        days_ago_created = days_ago_closed + random.randint(5, 20)
        
        tasks.append({
            "issue_key": f"IDLE-C{i+1}",
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
    print("📝 СОЗДАНИЕ ДАННЫХ ДЛЯ IDLE (НЕДОГРУЖЕННЫЙ ПРОЕКТ)")
    print("=" * 70)
    
    token_id = get_token_id()
    if not token_id:
        print("❌ Токен не найден!")
        return
    
    print(f"✅ Token ID: {token_id}")
    
    db = SessionLocal()
    
    try:
        # Очищаем старые данные
        print("\n🗑️ Очистка старых задач IDLE...")
        deleted = db.execute(text("DELETE FROM normalized.jira_issues WHERE project_key = 'IDLE'"))
        db.commit()
        print(f"   Удалено задач: {deleted.rowcount}")
        
        all_tasks = []
        
        print("\n👥 Генерация задач:")
        for dev in IDLE_TEAM["developers"]:
            tasks = generate_idle_tasks(dev["account_id"], dev["name"], token_id)
            all_tasks.extend(tasks)
            print(f"   {dev['name']}: {len(tasks)} задач")
        
        # Вставка в БД
        print(f"\n💾 Вставка {len(all_tasks)} задач...")
        
        for task in all_tasks:
            db.execute(text("""
                INSERT INTO normalized.jira_issues (
                    issue_key, project_key, summary, status, issue_type,
                    assignee_account_id, story_points, created_at, updated_at,
                    project_integration_id, is_deleted
                ) VALUES (
                    :issue_key, 'IDLE', :summary, :status, :issue_type,
                    :assignee_account_id, :story_points, :created_at, :updated_at,
                    :token_id, false
                )
            """), task)
        
        db.commit()
        
        # Статистика
        print("\n" + "=" * 70)
        print("📊 СТАТИСТИКА IDLE")
        print("=" * 70)
        
        result = db.execute(text("""
            SELECT 
                SUM(CASE WHEN status IN ('В работе', 'К выполнению') THEN story_points ELSE 0 END) as open_sp,
                SUM(CASE WHEN status = 'Готово' AND updated_at > NOW() - INTERVAL '28 days' THEN story_points ELSE 0 END) as closed_sp_4weeks,
                COUNT(*) as total_tasks,
                SUM(CASE WHEN status = 'Готово' THEN 1 ELSE 0 END) as closed_tasks
            FROM normalized.jira_issues
            WHERE project_key = 'IDLE'
        """)).fetchone()
        
        if result:
            open_sp = result[0] or 0
            closed_sp = result[1] or 0
            velocity = closed_sp / 4 if closed_sp > 0 else 1
            wi = open_sp / velocity if velocity > 0 else 0
            
            print(f"\n📈 Результат:")
            print(f"   Открытые задачи: {open_sp:.1f} SP")
            print(f"   Закрытые за 4 недели: {closed_sp:.1f} SP")
            print(f"   Velocity: {velocity:.1f} SP/неделю")
            print(f"   ** Workload Index: {wi:.2f} **")
            
            if wi < 0.7:
                print("   ✅ Цель достигнута (недогруз < 0.7)")
            else:
                print("   ⚠️ WI выше целевого (>0.7)")
        
        # Добавляем пользователя в проект IDLE
        print("\n🔗 Добавление пользователя в проект IDLE...")
        db.execute(text("""
            INSERT INTO core.user_projects (user_id, project_id, role)
            SELECT 
                u.id,
                p.id,
                'owner'
            FROM identity.users u
            CROSS JOIN core.projects p
            WHERE u.email = 'test.jira.test@yandex.ru'
            AND p.key = 'IDLE'
            AND NOT EXISTS (
                SELECT 1 FROM core.user_projects up 
                WHERE up.user_id = u.id AND up.project_id = p.id
            )
        """))
        db.commit()
        print("   ✅ Пользователь добавлен в проект IDLE")
        
        print("\n✅ Данные для IDLE созданы!")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()