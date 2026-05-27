# backend/scripts/create_test_data_bugs_yellow.py (исправленный)
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Создание данных для BUGS (желтый статус через workload 90%)
"""

import os
import sys
import random
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.session import SessionLocal
from sqlalchemy import text

BUGS_TEAM = {
    "developers": [
        {"name": "Алексей Иванов", "account_id": "712020:dc664c11-879e-4276-a1f2-ce3cc508e875"},
        {"name": "Елена Петрова", "account_id": "712020:ce4636a9-8a8a-4755-bed2-dd71f7dc501c"},
        {"name": "Михаил Сидоров", "account_id": "712020:c9c5639a-029c-4516-b211-5bfadebb550d"},
        {"name": "Екатерина Белова", "account_id": "712020:3a65ad05-5053-486f-ac67-88b8d7652d2a"}
    ],
    "qa": [
        {"name": "Павел Соколов", "account_id": "712020:0428a807-0aef-4b7d-b1cc-3fde971a5e1c"},
        {"name": "Наталья Лебедева", "account_id": "712020:2e7a65d1-6289-4b72-b480-f562838868e5"},
        {"name": "Мария Виноградова", "account_id": "712020:e00a96ff-008a-403f-bbd6-edb96280176e"}
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

def generate_bug_task(account_id, name, token_id, task_index):
    """Генерирует задачу с workload 90% (желтый) и SLA 68%"""
    
    is_bug = random.random() < 0.6
    issue_type = "Bug" if is_bug else "Task"
    sp = round(random.uniform(2, 5), 1)  # Увеличил SP для workload
    
    created_days_ago = random.randint(5, 25)
    created_at = datetime.now() - timedelta(days=created_days_ago)
    
    due_days_after = random.randint(5, 10)
    due_date = created_at + timedelta(days=due_days_after)
    
    # 68% в срок (желтый), 32% с опозданием
    rand = random.random()
    
    if rand < 0.68:  # В срок (68%)
        status = "Готово"
        closed_days_after = random.randint(1, due_days_after - 1)
        closed_at = created_at + timedelta(days=closed_days_after)
        updated_at = closed_at
    elif rand < 0.9:  # С опозданием (22%)
        status = "Готово"
        closed_days_after = due_days_after + random.randint(1, 7)
        closed_at = created_at + timedelta(days=closed_days_after)
        updated_at = closed_at
    else:  # Открыто (10%) - для увеличения workload
        status = random.choice(["В работе", "К выполнению"])
        closed_at = None
        updated_at = datetime.now()
    
    return {
        "issue_key": f"BUGS-{task_index}",
        "summary": f"[{issue_type}] {name}: Задача {task_index}",
        "status": status,
        "story_points": sp,
        "issue_type": issue_type,
        "assignee_account_id": account_id,
        "created_at": created_at,
        "updated_at": updated_at,
        "closed_at": closed_at,
        "due_date": due_date,
        "token_id": token_id
    }

def main():
    print("=" * 70)
    print("📝 BUGS - ЖЕЛТЫЙ СТАТУС (workload 90%, SLA 68%)")
    print("=" * 70)
    
    token_id = get_token_id()
    if not token_id:
        print("❌ Токен не найден!")
        return
    
    db = SessionLocal()
    
    try:
        db.execute(text("DELETE FROM normalized.jira_issues WHERE project_key = 'BUGS'"))
        db.commit()
        
        all_tasks = []
        task_counter = 1
        
        for dev in BUGS_TEAM["developers"]:
            for _ in range(8):  # Увеличил количество задач
                task = generate_bug_task(dev["account_id"], dev["name"], token_id, task_counter)
                all_tasks.append(task)
                task_counter += 1
        
        for qa in BUGS_TEAM["qa"]:
            for _ in range(6):
                task = generate_bug_task(qa["account_id"], qa["name"], token_id, task_counter)
                all_tasks.append(task)
                task_counter += 1
        
        for task in all_tasks:
            db.execute(text("""
                INSERT INTO normalized.jira_issues (
                    issue_key, project_key, summary, status, issue_type,
                    assignee_account_id, story_points, created_at, updated_at, closed_at, due_date,
                    project_integration_id, is_deleted
                ) VALUES (
                    :issue_key, 'BUGS', :summary, :status, :issue_type,
                    :assignee_account_id, :story_points, :created_at, :updated_at, :closed_at, :due_date,
                    :token_id, false
                )
            """), task)
        
        db.commit()
        
        # Статистика
        result = db.execute(text("""
            SELECT 
                SUM(CASE WHEN status IN ('В работе', 'К выполнению') THEN story_points ELSE 0 END) as open_sp,
                SUM(CASE WHEN status = 'Готово' AND updated_at > NOW() - INTERVAL '28 days' THEN story_points ELSE 0 END) as closed_sp_4weeks,
                COUNT(CASE WHEN status = 'Готово' AND closed_at <= due_date THEN 1 END) as on_time,
                COUNT(CASE WHEN status = 'Готово' THEN 1 END) as total_closed
            FROM normalized.jira_issues
            WHERE project_key = 'BUGS'
        """)).fetchone()
        
        if result:
            open_sp = result[0] or 0
            closed_sp = result[1] or 0
            velocity = closed_sp / 4 if closed_sp > 0 else 1
            wi = open_sp / velocity
            wi_percent = int(wi * 100)
            sla = round((result[2] / result[3] * 100) if result[3] > 0 else 0)
            
            print(f"\n📈 Workload: {wi_percent}% (цель 86-100% для желтого)")
            print(f"📈 SLA: {sla}%")
            
            if 86 <= wi_percent <= 100:
                print("   ✅ ЖЕЛТЫЙ СТАТУС (по workload)!")
            else:
                print(f"   ⚠️ Workload {wi_percent}%, ожидался 86-100%")
        
        print("\n✅ Данные для BUGS созданы!")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()