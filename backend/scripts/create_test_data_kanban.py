# backend/scripts/create_test_data_kanban_fixed2.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Создание ТЕСТОВЫХ данных в БД для KANBAN (WI = 0.7-1.2) - ИСПРАВЛЕННАЯ ВЕРСИЯ 2
Запуск: docker-compose exec backend python scripts/create_test_data_kanban_fixed2.py
"""

import os
import sys
import random
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.session import SessionLocal
from sqlalchemy import text

KANBAN_TEAM = {
    "developers": [
        {"name": "Ольга Волкова", "email": "olga.volkova@test.com", 
         "account_id": "712020:dc09232c-7ac3-4658-ba1a-248438416b52"},
        {"name": "Максим Васильев", "email": "maxim.vasiliev@test.com", 
         "account_id": "712020:4fcc4944-7521-46fb-a4a3-e3c4795eb856"},
        {"name": "Ирина Морозова", "email": "irina.morozova@test.com", 
         "account_id": "712020:fca64fca-b519-408f-97b2-6beef2c0b4b5"},
        {"name": "Андрей Соколов", "email": "andrey.sokolov@test.com", 
         "account_id": "712020:f3ba1b08-7826-4a70-bb44-0358f89b4952"}
    ],
    "qa": [
        {"name": "Павел Соколов", "email": "pavel.sokolov@test.com",
         "account_id": "712020:0428a807-0aef-4b7d-b1cc-3fde971a5e1c"}
    ]
}

KANBAN_STATUSES = ["Backlog", "Selected", "In Progress", "Review", "Done"]

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

def generate_kanban_tasks(account_id, name, token_id, task_index):
    """Генерирует задачи с правильным балансом открытых/закрытых"""
    
    # Для WI = 0.9:
    # На человека: 2-3 открытых задачи (SP ~2-4 каждая) → открыто ~8 SP
    # И 8-10 закрытых задач за 4 недели (SP ~3-5 каждая) → закрыто ~35 SP → velocity ~8.75 → WI = 8/8.75 = 0.91
    
    # 80% задач закрыты, 20% открыты
    rand = random.random()
    
    if rand < 0.8:  # Закрытые задачи
        status = "Done"
        sp = round(random.uniform(3, 6), 1)  # Крупные задачи
        days_ago_closed = random.randint(1, 28)
        days_ago_created = days_ago_closed + random.randint(3, 10)
        created_at = datetime.now() - timedelta(days=days_ago_created)
        updated_at = datetime.now() - timedelta(days=days_ago_closed)
        closed_at = updated_at
        due_date = created_at + timedelta(days=random.randint(3, 7))
    else:  # Открытые задачи - мало!
        open_statuses = ["Backlog", "Selected", "In Progress", "Review"]
        status = random.choice(open_statuses)
        sp = round(random.uniform(2, 4), 1)  # Небольшие задачи
        days_ago = random.randint(1, 7)
        created_at = datetime.now() - timedelta(days=days_ago)
        updated_at = datetime.now()
        closed_at = None
        due_date = None
    
    return {
        "issue_key": f"KANBAN-{task_index}",
        "summary": f"{name}: {status}",
        "status": status,
        "story_points": sp,
        "issue_type": "Task",
        "assignee_account_id": account_id,
        "created_at": created_at,
        "updated_at": updated_at,
        "closed_at": closed_at,
        "due_date": due_date,
        "token_id": token_id
    }

def main():
    print("=" * 70)
    print("📝 СОЗДАНИЕ ДАННЫХ ДЛЯ KANBAN (WI = 0.7-1.2)")
    print("=" * 70)
    
    token_id = get_token_id()
    if not token_id:
        print("❌ Токен не найден!")
        return
    
    print(f"✅ Token ID: {token_id}")
    
    db = SessionLocal()
    
    try:
        # Очищаем старые данные
        print("\n🗑️ Очистка старых задач KANBAN...")
        db.execute(text("DELETE FROM normalized.jira_issues WHERE project_key = 'KANBAN'"))
        db.commit()
        
        all_tasks = []
        task_counter = 1
        
        print("\n👥 Генерация задач (80% закрыты, 20% открыты)...")
        
        # Всего задач: 25-30 (не 38!)
        for dev in KANBAN_TEAM["developers"]:
            for _ in range(6):  # 6 задач на разработчика
                task = generate_kanban_tasks(dev["account_id"], dev["name"], token_id, task_counter)
                all_tasks.append(task)
                task_counter += 1
        
        for qa in KANBAN_TEAM["qa"]:
            for _ in range(5):  # 5 задач на QA
                task = generate_kanban_tasks(qa["account_id"], qa["name"], token_id, task_counter)
                all_tasks.append(task)
                task_counter += 1
        
        # Вставка в БД
        print(f"\n💾 Вставка {len(all_tasks)} задач...")
        
        for task in all_tasks:
            db.execute(text("""
                INSERT INTO normalized.jira_issues (
                    issue_key, project_key, summary, status, issue_type,
                    assignee_account_id, story_points, created_at, updated_at, closed_at, due_date,
                    project_integration_id, is_deleted
                ) VALUES (
                    :issue_key, 'KANBAN', :summary, :status, :issue_type,
                    :assignee_account_id, :story_points, :created_at, :updated_at, :closed_at, :due_date,
                    :token_id, false
                )
            """), task)
        
        db.commit()
        
        # Статистика
        print("\n" + "=" * 70)
        print("📊 СТАТИСТИКА KANBAN")
        print("=" * 70)
        
        result = db.execute(text("""
            SELECT status, COUNT(*) as count, SUM(story_points) as total_sp
            FROM normalized.jira_issues
            WHERE project_key = 'KANBAN'
            GROUP BY status
            ORDER BY 
                CASE status 
                    WHEN 'Backlog' THEN 1
                    WHEN 'Selected' THEN 2
                    WHEN 'In Progress' THEN 3
                    WHEN 'Review' THEN 4
                    WHEN 'Done' THEN 5
                END
        """)).fetchall()
        
        print("\nПо статусам:")
        for row in result:
            print(f"   {row[0]}: {row[1]} задач, {row[2]:.1f} SP")
        
        # WI расчёт
        result = db.execute(text("""
            SELECT 
                SUM(CASE WHEN status IN ('Backlog', 'Selected', 'In Progress', 'Review') THEN story_points ELSE 0 END) as open_sp,
                SUM(CASE WHEN status = 'Done' AND updated_at > NOW() - INTERVAL '28 days' THEN story_points ELSE 0 END) as closed_sp_4weeks,
                COUNT(CASE WHEN status IN ('Backlog', 'Selected', 'In Progress', 'Review') THEN 1 END) as open_count,
                COUNT(CASE WHEN status = 'Done' AND updated_at > NOW() - INTERVAL '28 days' THEN 1 END) as closed_count
            FROM normalized.jira_issues
            WHERE project_key = 'KANBAN'
        """)).fetchone()
        
        if result:
            open_sp = result[0] or 0
            closed_sp = result[1] or 0
            open_count = result[2] or 0
            closed_count = result[3] or 0
            velocity = closed_sp / 4 if closed_sp > 0 else 1
            wi = open_sp / velocity if velocity > 0 else 0
            
            print(f"\n📈 Расчёт WI:")
            print(f"   Открытые задачи: {open_count} шт, {open_sp:.1f} SP")
            print(f"   Закрытые за 4 недели: {closed_count} шт, {closed_sp:.1f} SP")
            print(f"   Velocity: {velocity:.1f} SP/неделю")
            print(f"   ** Workload Index: {wi:.2f} **")
            
            if 0.7 <= wi <= 1.2:
                print("   ✅ Цель достигнута (WI в пределах 0.7-1.2)")
            else:
                print(f"   ⚠️ WI {wi:.2f} выходит за пределы 0.7-1.2")
        
        # Добавляем пользователя в проект KANBAN
        db.execute(text("""
            INSERT INTO core.user_projects (user_id, project_id, role)
            SELECT 
                u.id,
                p.id,
                'owner'
            FROM identity.users u
            CROSS JOIN core.projects p
            WHERE u.email = 'test.jira.test@yandex.ru'
            AND p.key = 'KANBAN'
            AND NOT EXISTS (
                SELECT 1 FROM core.user_projects up 
                WHERE up.user_id = u.id AND up.project_id = p.id
            )
        """))
        db.commit()
        print("\n✅ Пользователь добавлен в проект KANBAN")
        
        print("\n✅ Данные для KANBAN созданы!")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()