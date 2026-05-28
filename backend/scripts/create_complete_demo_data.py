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
    # === LOW WORKLOAD (underloaded, success) ===
    "IDLE": {
        "name": "Документация",
        "description": "Поддержка документации",
        "category": "Documentation",
        "team": ["Ирина Морозова", "Ольга Волкова"],
        "qa": [],
        "issue_count": 20,
        "pr_count": 2,
        "profile": "low_activity",
        "avg_cycle_time_days": 7,
        "sla_target": 0.92,
        "bug_ratio": 0.05,
        "workflow": ["Аналитика", "Код", "Внедрение"],
        "open_ratio": 0.30,
        "closed_recent_ratio": 0.70
    },
    "NEWPROJ": {
        "name": "Исследование",
        "description": "R&D и исследования",
        "category": "Research",
        "team": ["Татьяна Кузьмина", "Сергей Новиков"],
        "qa": [],
        "issue_count": 10,
        "pr_count": 1,
        "profile": "new",
        "avg_cycle_time_days": 10,
        "sla_target": 0.95,
        "bug_ratio": 0.05,
        "workflow": ["Аналитика", "Код", "Внедрение"],
        "open_ratio": 0.30,
        "closed_recent_ratio": 0.80
    },
    
    # === MEDIUM-LOW WORKLOAD (optimal, success) ===
    "HEALTH": {
        "name": "Веб-Платформа",
        "description": "Разработка основной веб-платформы",
        "category": "Development",
        "team": ["Алексей Иванов", "Елена Петрова", "Михаил Сидоров", "Ольга Волкова", "Максим Васильев"],
        "qa": ["Павел Соколов", "Наталья Лебедева"],
        "issue_count": 45,
        "pr_count": 12,
        "profile": "healthy",
        "avg_cycle_time_days": 5,
        "sla_target": 0.95,
        "bug_ratio": 0.15,
        "workflow": ["Аналитика", "Код", "Ожидание ревью", "Тестирование", "Бизнес-тестирование", "Внедрение"],
        "open_ratio": 0.40,
        "closed_recent_ratio": 0.60
    },
    "KAN": {
        "name": "My Software Team",
        "description": "Разработка программного обеспечения",
        "category": "Development",
        "team": ["Алексей Иванов", "Максим Васильев", "Елена Петрова"],
        "qa": ["Павел Соколов", "Мария Виноградова"],
        "issue_count": 30,
        "pr_count": 8,
        "profile": "healthy",
        "avg_cycle_time_days": 5,
        "sla_target": 0.88,
        "bug_ratio": 0.15,
        "workflow": ["Аналитика", "Код", "Ожидание ревью", "Тестирование", "Внедрение"],
        "open_ratio": 0.40,
        "closed_recent_ratio": 0.60
    },
    "IMBAL": {
        "name": "API-Сервис",
        "description": "Разработка API для интеграций",
        "category": "Backend",
        "team": ["Михаил Сидоров", "Ольга Волкова", "Андрей Соколов"],
        "qa": ["Наталья Лебедева"],
        "issue_count": 55,
        "pr_count": 12,
        "profile": "imbalanced",
        "avg_cycle_time_days": 7,
        "sla_target": 0.75,
        "bug_ratio": 0.25,
        "workflow": ["Аналитика", "Код", "Ожидание ревью", "Тестирование", "Бизнес-тестирование", "Внедрение"],
        "open_ratio": 0.50,
        "closed_recent_ratio": 0.50
    },
    "KANBAN": {
        "name": "Операционные Задачи",
        "description": "Текущая операционная деятельность",
        "category": "Operations",
        "team": ["Ольга Волкова", "Максим Васильев", "Ирина Морозова", "Андрей Соколов", "Екатерина Белова"],
        "qa": ["Павел Соколов"],
        "issue_count": 50,
        "pr_count": 6,
        "profile": "kanban",
        "avg_cycle_time_days": 6,
        "sla_target": 0.80,
        "bug_ratio": 0.20,
        "workflow": ["Аналитика", "Код", "Ожидание ревью", "Тестирование", "Бизнес-тестирование", "Внедрение"],
        "open_ratio": 0.50,
        "closed_recent_ratio": 0.50
    },
    
    # === HIGH WORKLOAD (overloaded, error) ===
    "CRUNCH": {
        "name": "Мобильное Приложение",
        "description": "Разработка мобильного приложения под давлением",
        "category": "Mobile",
        "team": ["Максим Васильев", "Ирина Морозова", "Андрей Соколов"],
        "qa": ["Мария Виноградова"],
        "issue_count": 50,
        "pr_count": 8,
        "profile": "overloaded",
        "avg_cycle_time_days": 3,
        "sla_target": 0.70,
        "bug_ratio": 0.35,
        "workflow": ["Аналитика", "Код", "Ожидание ревью", "Тестирование", "Внедрение"],
        "open_ratio": 0.55,
        "closed_recent_ratio": 0.45
    },
    "BUGS": {
        "name": "Техподдержка",
        "description": "Поддержка и исправление багов",
        "category": "Support",
        "team": ["Алексей Иванов", "Елена Петрова", "Михаил Сидоров", "Екатерина Белова"],
        "qa": ["Павел Соколов", "Наталья Лебедева", "Мария Виноградова"],
        "issue_count": 45,
        "pr_count": 10,
        "profile": "buggy",
        "avg_cycle_time_days": 4,
        "sla_target": 0.75,
        "bug_ratio": 0.45,
        "workflow": ["Аналитика", "Код", "Ожидание ревью", "Тестирование", "Внедрение"],
        "open_ratio": 0.60,
        "closed_recent_ratio": 0.40
    },
    "EMAL": {
        "name": "(Example) Mobile App Launch",
        "description": "Запуск мобильного приложения",
        "category": "Mobile",
        "team": ["Алексей Иванов", "Елена Петрова", "Михаил Сидоров"],
        "qa": ["Павел Соколов"],
        "issue_count": 55,
        "pr_count": 10,
        "profile": "critical",
        "avg_cycle_time_days": 8,
        "sla_target": 0.60,
        "bug_ratio": 0.40,
        "workflow": ["Аналитика", "Код", "Ожидание ревью", "Тестирование", "Бизнес-тестирование", "Внедрение"],
        "open_ratio": 0.60,
        "closed_recent_ratio": 0.40
    },
    
    # === PROJECT WITH FULL CYCLE (for cycle time visualization) ===
    "FULLCYCLE": {
        "name": "Корпоративный Портал",
        "description": "Разработка корпоративного портала с полным циклом",
        "category": "Enterprise",
        "team": ["Алексей Иванов", "Елена Петрова", "Михаил Сидоров", "Ольга Волкова", "Максим Васильев", "Ирина Морозова"],
        "qa": ["Павел Соколов", "Наталья Лебедева", "Мария Виноградова"],
        "issue_count": 40,
        "pr_count": 15,
        "profile": "fullcycle",
        "avg_cycle_time_days": 6,
        "sla_target": 0.85,
        "bug_ratio": 0.20,
        "workflow": ["Аналитика", "Код", "Ожидание ревью", "Тестирование", "Бизнес-тестирование", "Внедрение"],
        "open_ratio": 0.60,
        "closed_recent_ratio": 0.40,
        "cycle_weights": {
            "Аналитика": 0.15,
            "Код": 0.35,
            "Ожидание ревью": 0.15,
            "Тестирование": 0.15,
            "Бизнес-тестирование": 0.15,
            "Внедрение": 0.05
        }
    }
}

# ============================================================
# ГЕНЕРАЦИЯ ДАННЫХ
# ============================================================

def get_or_create_project(db, project_key, project_name, jira_project_key):
    """Получает или создаёт проект в core.projects"""
    result = db.execute(
        text("SELECT id FROM core.projects WHERE key = :key"),
        {"key": project_key}
    ).fetchone()
    
    if result:
        return result[0]
    
    # Создаём проект
    result = db.execute(text("""
        INSERT INTO core.projects (key, name, jira_project_key, is_active, created_at, updated_at)
        VALUES (:key, :name, :jira_project_key, true, NOW(), NOW())
        RETURNING id
    """), {
        "key": project_key,
        "name": project_name,
        "jira_project_key": jira_project_key
    })
    db.commit()
    return result.fetchone()[0]


def ensure_user_project_link(db, project_id, user_id=1):
    """Создаёт связь пользователя с проектом если её нет"""
    result = db.execute(text("""
        SELECT id FROM core.user_projects 
        WHERE project_id = :project_id AND user_id = :user_id
    """), {"project_id": project_id, "user_id": user_id}).fetchone()
    
    if not result:
        db.execute(text("""
            INSERT INTO core.user_projects (user_id, project_id, role, created_at)
            VALUES (:user_id, :project_id, 'member', NOW())
        """), {"user_id": user_id, "project_id": project_id})
        db.commit()


def get_user_account_id(username):
    """Генерирует account_id на основе username (для тестовых данных)"""
    if not username:
        return None
    # Генерируем стабильный ID на основе имени
    hash_val = abs(hash(username))
    return f"{hash_val:08d}-{hash_val >> 16:04x}-{hash_val >> 32:04x}-8000-{hash_val >> 48:012x}"


def generate_changelog(issue_key, created_at, closed_at, workflow, config=None):
    """Генерирует историю переходов статусов с реалистичным временем"""
    changelog = []
    
    if not closed_at:
        # Задача не закрыта - только начальные переходы
        current_time = created_at
        max_statuses = min(2, len(workflow))
        for i in range(max_statuses):
            status = workflow[i]
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
        total_cycle_hours = (closed_at - created_at).total_seconds() / 3600
        
        # Done/Closed/Внедрение - БЫСТРЫЕ (1-3 часа), остальное распределяем
        done_status = workflow[-1]
        active_statuses = workflow[:-1]
        
        # Время на активные этапы = общее время - 1-3 часа на Done
        done_hours = random.uniform(1, 3)
        active_time = total_cycle_hours - done_hours
        
        if active_time < 0:
            active_time = total_cycle_hours * 0.8
            done_hours = total_cycle_hours * 0.2
        
        # Если есть веса для этапов (для FULLCYCLE)
        if config and "cycle_weights" in config:
            weights = config["cycle_weights"]
            # Пересчитываем веса без последнего статуса
            active_weights = {k: v for k, v in weights.items() if k in active_statuses}
            total_active_weight = sum(active_weights.values())
            
            for i, status in enumerate(workflow):
                changelog.append({
                    "issue_key": issue_key,
                    "field_name": "status",
                    "from_value": workflow[i-1] if i > 0 else None,
                    "to_value": status,
                    "changed_at": current_time,
                    "author_account_id": get_user_account_id(random.choice(["Алексей Иванов", "Елена Петрова"]))
                })
                
                if status == done_status:
                    # Done - быстро (1-3 часа)
                    current_time += timedelta(hours=done_hours)
                elif status in active_weights:
                    # Активные этапы - по весам
                    weight = active_weights[status] / total_active_weight
                    stage_hours = active_time * weight
                    stage_hours = stage_hours * random.uniform(0.7, 1.3)
                    current_time += timedelta(hours=stage_hours)
        else:
            # Обычные проекты - равномерное распределение
            hours_per_active = active_time / len(active_statuses) if active_statuses else active_time
            
            for i, status in enumerate(workflow):
                changelog.append({
                    "issue_key": issue_key,
                    "field_name": "status",
                    "from_value": workflow[i-1] if i > 0 else None,
                    "to_value": status,
                    "changed_at": current_time,
                    "author_account_id": get_user_account_id(random.choice(["Алексей Иванов", "Елена Петрова"]))
                })
                
                if status == done_status:
                    # Done - быстро
                    current_time += timedelta(hours=done_hours)
                elif status != workflow[-1]:
                    # Активные этапы
                    stage_hours = hours_per_active * random.uniform(0.7, 1.3)
                    current_time += timedelta(hours=stage_hours)
    
    return changelog


def generate_issue_data(project_key, config, issue_num, project_id, now, is_subtask=False, parent_id=None):
    """Генерирует данные для одной задачи с контролируемой загрузкой"""
    
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
    
    # Статус с учётом профиля загрузки
    workflow = config["workflow"]
    open_ratio = config.get("open_ratio", 0.35)
    closed_recent_ratio = config.get("closed_recent_ratio", 0.65)
    
    status_rand = random.random()
    
    if status_rand < open_ratio:
        # Открытые задачи (создают нагрузку)
        # Распределяем между начальными статусами
        if len(workflow) >= 3:
            status_idx = random.choice([0, 1, 2])
        elif len(workflow) >= 2:
            status_idx = random.choice([0, 1])
        else:
            status_idx = 0
        status = workflow[status_idx]
        is_closed = False
    else:
        # Закрытые задачи (не создают нагрузку)
        status = workflow[-1]
        is_closed = True
    
    # Назначенный пользователь
    all_team = config["team"] + config.get("qa", [])
    
    if random.random() < 0.15:
        # 15% задач не назначены
        assignee = None
    else:
        assignee = random.choice(all_team)
    
    # Даты (реалистичные)
    # Закрытые задачи - созданы недавно (чтобы попали в velocity за 2 недели)
    # Открытые задачи - могут быть старыми
    if is_closed:
        # Закрытая задача - создана 3-20 дней назад
        created_days_ago = random.randint(3, 20)
        created_at = now - timedelta(days=created_days_ago)
    else:
        # Открытая задача - может быть старой
        created_days_ago = random.randint(10, 90)
        created_at = now - timedelta(days=created_days_ago)
    
    if not is_closed:
        # Открытая задача
        updated_at = now
        closed_at = None
        # Для открытых задач - due_date в будущем или просрочена
        if random.random() < 0.3:
            # 30% просрочены
            due_date = now - timedelta(days=random.randint(1, 14))
        else:
            due_date = now + timedelta(days=random.randint(7, 30))
    else:
        # Закрытая задача
        # Распределяем по времени закрытия
        if random.random() < closed_recent_ratio:
            # Недавно закрытые (влияют на velocity) - ВСЕГДА в 2-недельном периоде
            closed_days_ago = random.randint(1, 5)
        else:
            # Закрытые раньше - но в 4-недельном периоде
            closed_days_ago = random.randint(8, 18)
        
        closed_at = now - timedelta(days=closed_days_ago)
        
        # Cycle time зависит от профиля
        avg_cycle = config.get("avg_cycle_time_days", 5)
        cycle_variation = random.uniform(0.5, 1.5)
        cycle_time_days = max(1, int(avg_cycle * cycle_variation))
        
        created_at = closed_at - timedelta(days=cycle_time_days)
        updated_at = closed_at  # ВАЖНО: для velocity calculation
        due_date = created_at + timedelta(days=random.randint(7, 30))
    
    # Story points - важно для workload calculation!
    # Открытые задачи - МАЛЕНЬКИЕ story points (меньше нагрузка)
    # Закрытые задачи - БОЛЬШИЕ story points (высокая velocity)
    if is_closed:
        # Закрытые задачи - большие story points = высокая velocity
        if issue_type == "Bug":
            story_points = random.choice([8, 13, 21])
        elif issue_type == "Story":
            story_points = random.choice([13, 21, 34])
        else:
            story_points = random.choice([8, 13, 21])
    else:
        # Открытые задачи - очень маленькие story points
        if issue_type == "Bug":
            story_points = random.choice([1, 2, 3])
        elif issue_type == "Story":
            story_points = random.choice([2, 3, 5])
        else:
            story_points = random.choice([2, 3, 5])
    
    # Время в работе (для тайм-трекинга)
    if is_closed:
        time_spent = random.randint(4, 40)
        remaining_estimate = 0  # Закрытые задачи - нет оставшегося времени
    else:
        time_spent = random.randint(1, 16)
        remaining_estimate = random.randint(2, 24)  # Оставшееся время для открытых
    
    # Оригинальная оценка (для расчёта прогресса)
    original_estimate = time_spent + remaining_estimate if remaining_estimate else time_spent * 2
    
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
    
    # Jira key
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
        "remaining_estimate": remaining_estimate,
        "original_estimate": original_estimate,
        "created_at": created_at,
        "updated_at": updated_at,
        "closed_at": closed_at,
        "due_date": due_date,
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
        # 1. ОЧИСТКА СТАРЫХ ДАННЫХ И КЭША
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
        
        # Очищаем кэш
        print("\n🗑️ Очистка кэша...")
        try:
            from app.services.cache_service import cache_service
            cache_service.clear()
            print("   ✅ Кэш очищен")
        except Exception as e:
            print(f"   ⚠️ Не удалось очистить кэш: {e}")
        
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
                {"status": "Аналитика", "is_open": True, "is_in_progress": False, "is_closed": False},
                {"status": "Код", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Ожидание ревью", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Тестирование", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Бизнес-тестирование", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Внедрение", "is_open": False, "is_in_progress": False, "is_closed": True},
            ],
            "CRUNCH": [
                {"status": "Аналитика", "is_open": True, "is_in_progress": False, "is_closed": False},
                {"status": "Код", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Ожидание ревью", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Тестирование", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Внедрение", "is_open": False, "is_in_progress": False, "is_closed": True},
            ],
            "BUGS": [
                {"status": "Аналитика", "is_open": True, "is_in_progress": False, "is_closed": False},
                {"status": "Код", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Ожидание ревью", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Тестирование", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Внедрение", "is_open": False, "is_in_progress": False, "is_closed": True},
            ],
            "KANBAN": [
                {"status": "Аналитика", "is_open": True, "is_in_progress": False, "is_closed": False},
                {"status": "Код", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Ожидание ревью", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Тестирование", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Бизнес-тестирование", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Внедрение", "is_open": False, "is_in_progress": False, "is_closed": True},
            ],
            "IDLE": [
                {"status": "Аналитика", "is_open": True, "is_in_progress": False, "is_closed": False},
                {"status": "Код", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Внедрение", "is_open": False, "is_in_progress": False, "is_closed": True},
            ],
            "EMAL": [
                {"status": "Аналитика", "is_open": True, "is_in_progress": False, "is_closed": False},
                {"status": "Код", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Ожидание ревью", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Тестирование", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Бизнес-тестирование", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Внедрение", "is_open": False, "is_in_progress": False, "is_closed": True},
            ],
            "IMBAL": [
                {"status": "Аналитика", "is_open": True, "is_in_progress": False, "is_closed": False},
                {"status": "Код", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Ожидание ревью", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Тестирование", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Бизнес-тестирование", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Внедрение", "is_open": False, "is_in_progress": False, "is_closed": True},
            ],
            "KAN": [
                {"status": "Аналитика", "is_open": True, "is_in_progress": False, "is_closed": False},
                {"status": "Код", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Ожидание ревью", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Тестирование", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Внедрение", "is_open": False, "is_in_progress": False, "is_closed": True},
            ],
            "NEWPROJ": [
                {"status": "Аналитика", "is_open": True, "is_in_progress": False, "is_closed": False},
                {"status": "Код", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Внедрение", "is_open": False, "is_in_progress": False, "is_closed": True},
            ],
            "FULLCYCLE": [
                {"status": "Аналитика", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Код", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Ожидание ревью", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Тестирование", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Бизнес-тестирование", "is_open": True, "is_in_progress": True, "is_closed": False},
                {"status": "Внедрение", "is_open": False, "is_in_progress": False, "is_closed": True},
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
            project_id = get_or_create_project(db, project_key, config["name"], project_key)
            if not project_id:
                print(f"   ⚠️ Не удалось создать проект {project_key}, пропускаем")
                continue
            
            # Создаём связь с пользователем
            ensure_user_project_link(db, project_id)
            
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
                        config["workflow"],
                        config=config
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
                        remaining_estimate, original_estimate,
                        created_at, updated_at, closed_at, due_date,
                        parent_issue_id, last_synced_at, is_deleted
                    ) VALUES (
                        :id, :issue_key, :project_key, :summary,
                        :issue_type, :status, :priority, :assignee_account_id,
                        :assignee_name, :story_points, :time_spent,
                        :remaining_estimate, :original_estimate,
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
                    "remaining_estimate": issue.get("remaining_estimate"),
                    "original_estimate": issue.get("original_estimate"),
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
            project_id = get_or_create_project(db, project_key, config["name"], project_key)
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
