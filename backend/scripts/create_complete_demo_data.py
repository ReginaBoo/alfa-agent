#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
УНИВЕРСАЛЬНЫЙ СКРИПТ ДЛЯ ГЕНЕРАЦИИ ПОЛНЫХ ТЕСТОВЫХ ДАННЫХ

Создаёт реалистичные данные для демонстрации всех функций фронтенда:
- Jira задачи с разными статусами, assignees, датами
- GitHub PRs, Commits, Reviews
- Confluence страницы (опционально)
- Changelog для задач (история переходов статусов)

Запуск: docker exec -i backend-backend-1 python scripts/create_complete_demo_data.py
Или локально: python backend/scripts/create_complete_demo_data.py
"""

import sys
import os
import random
import json
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from sqlalchemy import text

# ============================================================
# КОНФИГУРАЦИЯ ПРОЕКТОВ
# ============================================================

PROJECTS_CONFIG = {
    "HEALTH": {
        "name": "Веб-Платформа",
        "description": "Разработка основной веб-платформы",
        "category": "Development",
        "team": ["Алексей Иванов", "Елена Петрова", "Михаил Сидоров", "Ольга Волкова", "Максим Васильев"],
        "qa": ["Павел Соколов", "Наталья Лебедева"],
        "issue_count": 50,
        "pr_count": 15,
        "profile": "healthy",
        "avg_cycle_time_days": 5,
        "sla_target": 0.95,
        "bug_ratio": 0.2,
        "workflow": ["To Do", "In Progress", "Code Review", "Testing", "Done"]
    },
    "CRUNCH": {
        "name": "Мобильное Приложение",
        "description": "Разработка мобильного приложения под давлением",
        "category": "Mobile",
        "team": ["Максим Васильев", "Ирина Морозова", "Андрей Соколов"],
        "qa": ["Мария Виноградова"],
        "issue_count": 60,
        "pr_count": 8,
        "profile": "overloaded",
        "avg_cycle_time_days": 3,
        "sla_target": 0.40,
        "bug_ratio": 0.5,
        "workflow": ["To Do", "In Progress", "Done"]
    },
    "BUGS": {
        "name": "Техподдержка",
        "description": "Поддержка и исправление багов",
        "category": "Support",
        "team": ["Алексей Иванов", "Елена Петрова", "Михаил Сидоров", "Екатерина Белова"],
        "qa": ["Павел Соколов", "Наталья Лебедева", "Мария Виноградова"],
        "issue_count": 50,
        "pr_count": 10,
        "profile": "buggy",
        "avg_cycle_time_days": 4,
        "sla_target": 0.55,
        "bug_ratio": 0.7,
        "workflow": ["New", "In Progress", "Resolved", "Closed"]
    },
    "KANBAN": {
        "name": "Операционные Задачи",
        "description": "Текущая операционная деятельность",
        "category": "Operations",
        "team": ["Ольга Волкова", "Максим Васильев", "Ирина Морозова", "Андрей Соколов"],
        "qa": ["Павел Соколов"],
        "issue_count": 40,
        "pr_count": 5,
        "profile": "kanban",
        "avg_cycle_time_days": 6,
        "sla_target": 0.85,
        "bug_ratio": 0.3,
        "workflow": ["Backlog", "Selected", "In Progress", "Review", "Done"]
    },
    "IDLE": {
        "name": "Документация",
        "description": "Техническая документация и R&D",
        "category": "Documentation",
        "team": ["Сергей Новиков", "Татьяна Кузьмина"],
        "qa": [],
        "issue_count": 20,
        "pr_count": 3,
        "profile": "underloaded",
        "avg_cycle_time_days": 10,
        "sla_target": 1.0,
        "bug_ratio": 0.1,
        "workflow": ["To Do", "In Progress", "Done"]
    },
    "EMAL": {
        "name": "(Example) Mobile App Launch",
        "description": "Запуск мобильного приложения",
        "category": "Mobile",
        "team": ["Алексей Иванов", "Елена Петрова"],
        "qa": ["Павел Соколов"],
        "issue_count": 30,
        "pr_count": 8,
        "profile": "healthy",
        "avg_cycle_time_days": 6,
        "sla_target": 0.90,
        "bug_ratio": 0.25,
        "workflow": ["To Do", "In Progress", "Done"]
    },
    "IMBAL": {
        "name": "API-Сервис",
        "description": "Разработка API для интеграций",
        "category": "Backend",
        "team": ["Михаил Сидоров", "Ольга Волкова"],
        "qa": ["Наталья Лебедева"],
        "issue_count": 35,
        "pr_count": 10,
        "profile": "imbalanced",
        "avg_cycle_time_days": 7,
        "sla_target": 0.70,
        "bug_ratio": 0.3,
        "workflow": ["To Do", "In Progress", "Code Review", "Done"]
    },
    "KAN": {
        "name": "My Software Team",
        "description": "Разработка программного обеспечения",
        "category": "Development",
        "team": ["Алексей Иванов", "Максим Васильев", "Елена Петрова"],
        "qa": ["Павел Соколов", "Мария Виноградова"],
        "issue_count": 25,
        "pr_count": 6,
        "profile": "healthy",
        "avg_cycle_time_days": 5,
        "sla_target": 0.88,
        "bug_ratio": 0.2,
        "workflow": ["Backlog", "In Progress", "Review", "Done"]
    },
    "NEWPROJ": {
        "name": "Исследование",
        "description": "R&D и исследования",
        "category": "Research",
        "team": ["Татьяна Кузьмина", "Сергей Новиков"],
        "qa": [],
        "issue_count": 12,
        "pr_count": 2,
        "profile": "new",
        "avg_cycle_time_days": 14,
        "sla_target": None,
        "bug_ratio": 0.1,
        "workflow": ["To Do", "In Progress", "Done"]
    }
}

# ============================================================
# ГЕНЕРАЦИЯ ДАННЫХ
# ============================================================

def get_project_id(db, project_key):
    """Получает ID проекта по его ключу"""
    result = db.execute(
        text("SELECT id FROM core.projects WHERE key = :key"),
        {"key": project_key}
    ).fetchone()
    return result[0] if result else None


def get_user_account_id(username):
    """Генерирует account_id на основе username (для тестовых данных)"""
    if not username:
        return None
    # Генерируем стабильный ID на основе имени
    hash_val = abs(hash(username))
    return f"{hash_val:08d}-{hash_val >> 16:04x}-{hash_val >> 32:04x}-8000-{hash_val >> 48:012x}"


def generate_changelog(issue_key, created_at, closed_at, workflow):
    """Генерирует историю переходов статусов"""
    changelog = []
    
    if not closed_at:
        # Задача не закрыта - только начальные переходы
        current_time = created_at
        for i, status in enumerate(workflow[:2]):  # Только первые 2 статуса
            changelog.append({
                "issue_key": issue_key,
                "field_name": "status",
                "from_value": workflow[i-1] if i > 0 else None,
                "to_value": status,
                "changed_at": current_time,
                "author_account_id": get_user_account_id(random.choice(["Алексей Иванов", "Елена Петрова"]))
            })
            current_time += timedelta(hours=random.randint(2, 24))
    else:
        # Задача закрыта - полный цикл
        current_time = created_at
        for status in workflow:
            changelog.append({
                "issue_key": issue_key,
                "field_name": "status",
                "from_value": workflow[workflow.index(status) - 1] if workflow.index(status) > 0 else None,
                "to_value": status,
                "changed_at": current_time,
                "author_account_id": get_user_account_id(random.choice(["Алексей Иванов", "Елена Петрова"]))
            })
            if status != workflow[-1]:
                current_time += timedelta(hours=random.randint(4, 48))
    
    return changelog


def generate_issue_data(project_key, config, issue_num, project_id, now, is_subtask=False, parent_id=None):
    """Генерирует данные для одной задачи"""
    
    # Тип задачи
    if is_subtask:
        issue_type = "Sub-task"
        prefix = "Sub"
    elif random.random() < config["bug_ratio"]:
        issue_type = "Bug"
        prefix = "Bug"
    elif random.random() < 0.3:
        issue_type = "Story"
        prefix = "Story"
    else:
        issue_type = "Task"
        prefix = "Task"
    
    # Приоритет
    priority = random.choice(["Low", "Medium", "High", "High", "Critical"])
    
    # Статус (распределение по воркфлоу)
    workflow = config["workflow"]
    # РЕАЛИСТИЧНОЕ РАСПРЕДЕЛЕНИЕ ДЛЯ WORKLOAD 40-120%:
    # - 15% открытых (To Do, In Progress) - создают нагрузку
    # - 10% в работе (Code Review, Testing)
    # - 75% закрытых (Done, Closed, Resolved) - показывают высокую velocity
    
    status_rand = random.random()
    if status_rand < 0.15:
        # Открытые задачи (первые 2 статуса workflow)
        status_idx = random.choice([0, 1] if len(workflow) >= 2 else [0])
    elif status_rand < 0.25:
        # В процессе (средние статусы)
        if len(workflow) >= 4:
            status_idx = random.choice([2, 3])
        elif len(workflow) >= 3:
            status_idx = 1
        else:
            status_idx = 0
    else:
        # Закрытые задачи (последний статус) - ПОВЫСИЛИ до 75%
        status_idx = len(workflow) - 1
    
    status = workflow[status_idx]
    
    # Назначенный пользователь - распределяем неравномерно!
    all_team = config["team"] + config.get("qa", [])
    
    # Для реалистичности: не всем назначаем задачи равномерно
    # Некоторые получают больше, некоторые меньше
    if random.random() < 0.3:
        # 30% случаев - задача не назначена
        assignee = None
    elif random.random() < 0.2 and len(all_team) > 1:
        # 20% случаев - назначаем "любимчика" (кто уже имеет много задач)
        # Для простоты - просто выбираем из первых 2 человек
        assignee = random.choice(all_team[:2])
    else:
        assignee = random.choice(all_team)
    
    # Даты (реалистичные)
    created_days_ago = random.randint(30, 90)  # Задачи созданы 30-90 дней назад
    created_at = now - timedelta(days=created_days_ago)
    
    # Если задача не закрыта, updated_at = сейчас
    if status not in ["Done", "Closed", "Resolved", "Готово"]:
        updated_at = now
        closed_at = None
    else:
        # Закрытая задача - закрыта в последние 14 дней (для высокой velocity!)
        # 80% закрытых задач закрыты за последние 14 дней
        if random.random() < 0.8:
            closed_days_ago = random.randint(1, 14)
            closed_at = now - timedelta(days=closed_days_ago)
        else:
            # 20% закрыты раньше (для истории)
            closed_days_ago = random.randint(15, 60)
            closed_at = now - timedelta(days=closed_days_ago)
        
        # Cycle time = 3-10 дней
        cycle_time_days = random.randint(3, 10)
        created_at = closed_at - timedelta(days=cycle_time_days)
        updated_at = closed_at
    
    # Оценка (story points) - только для родительских задач
    story_points = random.choice([1, 2, 3, 5, 8, 13]) if issue_type != "Bug" and not is_subtask else None
    
    # Время в работе
    time_spent = random.randint(2, 24) if random.random() > 0.3 else None
    
    # Описание
    summaries = {
        "Bug": [
            f"[{prefix}-{issue_num}] Критическая ошибка в модуле аутентификации",
            f"[{prefix}-{issue_num}] Исправление утечки памяти в background workers",
            f"[{prefix}-{issue_num}] Исправление проблемы с кэшированием",
            f"[{prefix}-{issue_num}] Ошибка валидации данных в API",
            f"[{prefix}-{issue_num}] Проблемы с производительностью базы данных"
        ],
        "Story": [
            f"[{prefix}-{issue_num}] Добавить новую функцию экспорта данных",
            f"[{prefix}-{issue_num}] Реализовать темную тему интерфейса",
            f"[{prefix}-{issue_num}] Улучшить UX мобильного приложения",
            f"[{prefix}-{issue_num}] Интеграция с внешними сервисами"
        ],
        "Task": [
            f"[Этап {issue_num}] Разработка модуля",
            f"[Этап {issue_num}] Тестирование функционала",
            f"[Этап {issue_num}] Документирование API",
            f"[Этап {issue_num}] Настройка инфраструктуры"
        ],
        "Sub-task": [
            f"[{prefix}-{issue_num}] Сбор требований и ТЗ",
            f"[{prefix}-{issue_num}] Проектирование базы данных",
            f"[{prefix}-{issue_num}] Написание unit тестов",
            f"[{prefix}-{issue_num}] Код-ревью",
            f"[{prefix}-{issue_num}] Деплой на staging"
        ]
    }
    
    summary = random.choice(summaries[issue_type])
    
    # Jira key (генерируем ПОСЛЕДОВАТЕЛЬНО для уникальности)
    issue_key = f"{project_key}-{issue_num}"
    
    return {
        "issue_key": issue_key,
        "project_key": project_key,
        "project_id": project_id,
        "summary": summary,
        "issue_type": issue_type,
        "status": status,
        "priority": priority,
        "assignee": assignee,
        "story_points": story_points,
        "time_spent": time_spent,
        "created_at": created_at,
        "updated_at": updated_at,
        "closed_at": closed_at,
        "due_date": created_at + timedelta(days=random.randint(7, 30)) if random.random() > 0.5 else None,
        "parent_issue_id": parent_id
    }



def main():
    print("=" * 70)
    print("🚀 ГЕНЕРАЦИЯ ПОЛНЫХ ТЕСТОВЫХ ДАННЫХ ДЛЯ ДЕМО")
    print("=" * 70)
    
    db = SessionLocal()
    now = datetime.now()
    
    try:
        # ============================================================
        # 1. ОЧИСТКА СТАРЫХ ДАННЫХ
        # ============================================================
        print("\n🗑️ Очистка старых данных...")
        db.execute(text("DELETE FROM normalized.project_status_mappings"))
        db.execute(text("DELETE FROM normalized.issue_changelog"))
        db.execute(text("DELETE FROM normalized.jira_issues"))
        db.execute(text("DELETE FROM normalized.github_pull_request_reviews"))
        db.execute(text("DELETE FROM normalized.github_commits"))
        db.execute(text("DELETE FROM normalized.github_pull_requests"))
        db.execute(text("DELETE FROM normalized.confluence_comments"))
        db.execute(text("DELETE FROM normalized.confluence_pages"))
        db.commit()
        print("   ✅ Удалено")
        
        # Добавим ещё раз для уверенности (в случае если были дубли)
        print("   🔄 Дополнительная очистка Jira задач...")
        db.execute(text("DELETE FROM normalized.jira_issues WHERE is_deleted = false"))
        db.commit()
        print("   ✅ Готово")
        
        # ============================================================
        # 1.5. СОЗДАЁМ STATUS MAPPINGS ДЛЯ КАЖДОГО ПРОЕКТА
        # ============================================================
        print("\n🔧 Создание status mappings...")
        
        from app.db.models.normalized import ProjectStatusMapping
        
        status_mappings = {
            "HEALTH": [
                {"status": "To Do", "is_open": True, "is_in_progress": False, "is_closed": False},
                {"status": "In Progress", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Code Review", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Testing", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Done", "is_open": False, "is_in_progress": False, "is_closed": True},
            ],
            "CRUNCH": [
                {"status": "To Do", "is_open": True, "is_in_progress": False, "is_closed": False},
                {"status": "In Progress", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Done", "is_open": False, "is_in_progress": False, "is_closed": True},
            ],
            "BUGS": [
                {"status": "New", "is_open": True, "is_in_progress": False, "is_closed": False},
                {"status": "In Progress", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Resolved", "is_open": False, "is_in_progress": False, "is_closed": True},
                {"status": "Closed", "is_open": False, "is_in_progress": False, "is_closed": True},
            ],
            "KANBAN": [
                {"status": "Backlog", "is_open": True, "is_in_progress": False, "is_closed": False},
                {"status": "Selected", "is_open": True, "is_in_progress": False, "is_closed": False},
                {"status": "In Progress", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Review", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Done", "is_open": False, "is_in_progress": False, "is_closed": True},
            ],
            "IDLE": [
                {"status": "To Do", "is_open": True, "is_in_progress": False, "is_closed": False},
                {"status": "In Progress", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Done", "is_open": False, "is_in_progress": False, "is_closed": True},
            ],
            "EMAL": [
                {"status": "To Do", "is_open": True, "is_in_progress": False, "is_closed": False},
                {"status": "In Progress", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Done", "is_open": False, "is_in_progress": False, "is_closed": True},
            ],
            "IMBAL": [
                {"status": "To Do", "is_open": True, "is_in_progress": False, "is_closed": False},
                {"status": "In Progress", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Code Review", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Done", "is_open": False, "is_in_progress": False, "is_closed": True},
            ],
            "KAN": [
                {"status": "Backlog", "is_open": True, "is_in_progress": False, "is_closed": False},
                {"status": "In Progress", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Review", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Done", "is_open": False, "is_in_progress": False, "is_closed": True},
            ],
            "NEWPROJ": [
                {"status": "To Do", "is_open": True, "is_in_progress": False, "is_closed": False},
                {"status": "In Progress", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Done", "is_open": False, "is_in_progress": False, "is_closed": True},
            ],
        }
        
        for project_key, mappings in status_mappings.items():
            for mapping in mappings:
                db.execute(text("""
                    INSERT INTO normalized.project_status_mappings (
                        project_key, status_name, is_open, is_in_progress, is_closed,
                        last_synced_at
                    ) VALUES (
                        :project_key, :status_name, :is_open, :is_in_progress, :is_closed,
                        :last_synced
                    )
                    ON CONFLICT (project_key, status_name) DO UPDATE SET
                        is_open = EXCLUDED.is_open,
                        is_in_progress = EXCLUDED.is_in_progress,
                        is_closed = EXCLUDED.is_closed,
                        last_synced_at = EXCLUDED.last_synced_at
                """), {
                    "project_key": project_key,
                    "status_name": mapping["status"],
                    "is_open": mapping["is_open"],
                    "is_in_progress": mapping["is_in_progress"],
                    "is_closed": mapping["is_closed"],
                    "last_synced": now
                })
        
        db.commit()
        print("   ✅ Status mappings созданы")
        
        # ============================================================
        # 2. ГЕНЕРАЦИЯ JIRA ЗАДАЧ
        # ============================================================
        print("\n📝 Генерация Jira задач...")
        
        all_issues = []
        all_changelogs = []
        issue_id = 1000
        
        for project_key, config in PROJECTS_CONFIG.items():
            project_id = get_project_id(db, project_key)
            if not project_id:
                print(f"   ⚠️ Проект {project_key} не найден, пропускаем")
                continue
            
            print(f"   📁 {project_key}: {config['issue_count']} задач")
            
            parent_task_id = None
            parent_issue_key = None
            
            for i in range(config["issue_count"]):
                # 30% задач - родительские (этапы), 70% - подзадачи
                is_subtask = (parent_task_id is not None and random.random() < 0.7)
                
                if is_subtask:
                    # Генерируем подзадачу
                    issue = generate_issue_data(
                        project_key, config, 
                        issue_num=i+1, 
                        project_id=project_id, 
                        now=now,
                        is_subtask=True,
                        parent_id=parent_task_id
                    )
                else:
                    # Генерируем родительскую задачу
                    issue = generate_issue_data(
                        project_key, config, 
                        issue_num=i+1, 
                        project_id=project_id, 
                        now=now,
                        is_subtask=False,
                        parent_id=None
                    )
                    parent_task_id = issue_id  # Сохраняем ID для следующих подзадач
                    parent_issue_key = issue["issue_key"]
                
                issue["id"] = issue_id
                all_issues.append(issue)
                
                # Генерируем changelog только для родительских задач
                if not is_subtask:
                    changelog = generate_changelog(
                        issue["issue_key"],
                        issue["created_at"],
                        issue["closed_at"],
                        config["workflow"]
                    )
                    all_changelogs.extend(changelog)
                
                issue_id += 1
                
                # Сбрасываем parent после 2-3 подзадач
                if parent_task_id and (i + 1) % random.randint(2, 3) == 0:
                    parent_task_id = None
        
        # Вставляем задачи
        print(f"\n💾 Вставка {len(all_issues)} задач Jira...")
        for issue in all_issues:
            try:
                db.execute(text("""
                    INSERT INTO normalized.jira_issues (
                        id, issue_key, project_key, summary,
                        issue_type, status, priority, assignee_account_id,
                        assignee_name, story_points, time_spent,
                        created_at, updated_at, closed_at, due_date,
                        parent_issue_id, last_synced_at, is_deleted
                    ) VALUES (
                        :id, :issue_key, :project_key, :summary,
                        :issue_type, :status, :priority, :assignee_account_id,
                        :assignee_name, :story_points, :time_spent,
                        :created_at, :updated_at, :closed_at, :due_date,
                        :parent_issue_id, :last_synced, :is_deleted
                    )
                """), {
                    "id": issue["id"],
                    "issue_key": issue["issue_key"],
                    "project_key": issue["project_key"],
                    "summary": issue["summary"],
                    "issue_type": issue["issue_type"],
                    "status": issue["status"],
                    "priority": issue["priority"],
                    "assignee_account_id": get_user_account_id(issue["assignee"]) if issue["assignee"] else None,
                    "assignee_name": issue["assignee"] if issue["assignee"] else None,
                    "story_points": issue["story_points"],
                    "time_spent": issue["time_spent"],
                    "created_at": issue["created_at"],
                    "updated_at": issue["updated_at"],
                    "closed_at": issue["closed_at"],
                    "due_date": issue["due_date"],
                    "parent_issue_id": issue.get("parent_issue_id"),
                    "last_synced": now,
                    "is_deleted": False
                })
            except Exception as e:
                print(f"   ⚠️ Ошибка при вставке {issue['issue_key']}: {e}")
        
        # Вставляем changelog
        print(f"💾 Вставка {len(all_changelogs)} записей changelog...")
        changelog_id = 10000
        for log in all_changelogs:
            db.execute(text("""
                INSERT INTO normalized.issue_changelog (
                    id, issue_key, field_name, from_value, to_value,
                    changed_at, author_account_id, created_at
                ) VALUES (
                    :id, :issue_key, :field_name, :from_value, :to_value,
                    :changed_at, :author_account_id, :created_at
                )
            """), {
                "id": changelog_id,
                "issue_key": log["issue_key"],
                "field_name": log["field_name"],
                "from_value": log["from_value"],
                "to_value": log["to_value"],
                "changed_at": log["changed_at"],
                "author_account_id": log["author_account_id"],
                "created_at": log["changed_at"]
            })
            changelog_id += 1
        
        db.commit()
        
        # ============================================================
        # 3. ГЕНЕРАЦИЯ GITHUB PRs, COMMITS, REVIEWS
        # ============================================================
        print("\n📝 Генерация GitHub данных...")
        
        # Вставляем PRs и коммиты (используем существующий скрипт)
        from scripts.create_real_github_data import main as generate_github_data
        generate_github_data()
        
        # ============================================================
        # 4. ГЕНЕРАЦИЯ CONFLUENCE СТРАНИЦ
        # ============================================================
        print("\n📄 Генерация Confluence страниц...")
        
        page_id = 1
        for project_key, config in PROJECTS_CONFIG.items():
            project_id = get_project_id(db, project_key)
            if not project_id:
                continue
            
            # Создаём 2-3 страницы на проект
            for i in range(random.randint(2, 3)):
                page_created = now - timedelta(days=random.randint(10, 60))
                
                db.execute(text("""
                    INSERT INTO normalized.confluence_pages (
                        id, space_id, space_key, title, author_id,
                        author_name, version, status, content,
                        created_at, updated_at, last_synced_at,
                        is_deleted
                    ) VALUES (
                        :id, :space_id, :space_key, :title, :author_id,
                        :author_name, :version, :status, :content,
                        :created_at, :updated_at, :last_synced,
                        :is_deleted
                    )
                """), {
                    "id": f"PAGE-{page_id}",
                    "space_id": f"SPACE-{project_id}",
                    "space_key": project_key,
                    "title": f"{config['name']} - Документация {i+1}",
                    "author_id": get_user_account_id(random.choice(config["team"])),
                    "author_name": random.choice(config["team"]),
                    "version": random.randint(1, 5),
                    "status": "current",
                    "content": f"<p>Техническая документация для проекта {config['name']}</p>",
                    "created_at": page_created,
                    "updated_at": page_created + timedelta(days=random.randint(1, 20)),
                    "last_synced": now,
                    "is_deleted": False
                })
                page_id += 1
        
        db.commit()
        
        # ============================================================
        # 5. СТАТИСТИКА
        # ============================================================
        print("\n" + "=" * 70)
        print("📊 ИТОГОВАЯ СТАТИСТИКА")
        print("=" * 70)
        
        stats = db.execute(text("""
            SELECT 
                p.key,
                COUNT(DISTINCT ji.id) as issues,
                COUNT(DISTINCT CASE WHEN ji.status IN ('Done', 'Closed', 'Resolved', 'Готово') THEN ji.id END) as closed,
                COUNT(DISTINCT pr.id) as prs,
                COUNT(DISTINCT c.id) as commits
            FROM core.projects p
            LEFT JOIN normalized.jira_issues ji ON ji.project_key = p.jira_project_key AND ji.is_deleted = false
            LEFT JOIN normalized.github_pull_requests pr ON pr.project_id = p.id
            LEFT JOIN normalized.github_commits c ON c.project_id = p.id
            GROUP BY p.key
            ORDER BY p.key
        """)).fetchall()
        
        print("\n📈 Данные по проектам:")
        print(f"   {'Проект':<10} {'Задач':>8} {'Закрыто':>10} {'PR':>6} {'Commits':>10}")
        print("   " + "-" * 50)
        for row in stats:
            print(f"   {row[0]:<10} {row[1]:>8} {row[2]:>10} {row[3]:>6} {row[4]:>10}")
        
        print("\n💡 Готово! Данные для всех метрик:")
        print("   ✅ Cycle Time (через changelog)")
        print("   ✅ Lead Time")
        print("   ✅ SLA Score")
        print("   ✅ Workload Index")
        print("   ✅ PR Metrics")
        print("   ✅ Health Score")
        print("\n🎯 Можешь запускать фронтенд и смотреть демо!")
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()
