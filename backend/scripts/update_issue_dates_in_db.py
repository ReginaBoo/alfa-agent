#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_issue_dates_in_db.py

Обновляет даты создания и обновления задач в локальной БД на реалистичные
с учётом характеристик проектов.

Запуск: docker-compose exec backend python scripts/update_issue_dates_in_db.py
"""

import sys
import os
import random
from datetime import datetime, timedelta
from typing import Dict, List

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.db.session import SessionLocal
from config import TEST_PROJECTS


def print_info(msg: str): print(f"INFO: {msg}")
def print_success(msg: str): print(f"✅ {msg}")
def print_warn(msg: str): print(f"⚠️  {msg}")
def print_error(msg: str): print(f"❌ {msg}")


def get_project_config_by_key(project_key: str) -> dict:
    """Возвращает конфигурацию проекта"""
    for project in TEST_PROJECTS:
        if project.get('key') == project_key:
            return project
    return {}


def get_target_workload(project_key: str) -> float:
    """Возвращает целевую загрузку для проекта"""
    config = get_project_config_by_key(project_key)
    return config.get('workload_target', 0.85)


def get_projects(db) -> List[str]:
    """Получает список проектов из БД"""
    result = db.execute(text("""
        SELECT DISTINCT project_key 
        FROM normalized.jira_issues 
        ORDER BY project_key
    """))
    return [row[0] for row in result.fetchall()]


def get_project_issues(db, project_key: str) -> List[Dict]:
    """Получает задачи проекта"""
    result = db.execute(text("""
        SELECT issue_key, created_at, updated_at, status
        FROM normalized.jira_issues 
        WHERE project_key = :project_key
    """), {"project_key": project_key})
    
    return [{"key": row[0], "created": row[1], "updated": row[2], "status": row[3]} 
            for row in result.fetchall()]


def get_weeks_back_for_project(project_key: str) -> int:
    """Определяет, насколько старые задачи создавать в зависимости от целевой загрузки"""
    target_wi = get_target_workload(project_key)
    
    if target_wi > 1.2:
        # Перегруженный проект — много старых задач (3-5 месяцев)
        return random.randint(12, 20)
    elif target_wi > 0.9:
        # Повышенная нагрузка (2-3.5 месяца)
        return random.randint(8, 14)
    elif target_wi < 0.6:
        # Недогруженный проект — свежие задачи (0.5-1.5 месяца)
        return random.randint(2, 6)
    else:
        # Нормальная загрузка (1-2.5 месяца)
        return random.randint(4, 10)


def get_random_date_for_issue(
    issue_num: int, 
    total_issues: int, 
    weeks_back: int,
    target_wi: float
) -> datetime:
    """
    Генерирует случайную дату для задачи с учётом целевой загрузки.
    """
    today = datetime.now()
    
    # Чем выше целевая загрузка, тем больше старых задач
    if target_wi > 1.2:
        # Перегруз: больше старых задач
        skew_factor = 1.3
    elif target_wi < 0.6:
        # Недогруз: больше новых задач
        skew_factor = 0.7
    else:
        skew_factor = 1.0
    
    progress = (issue_num / total_issues) ** skew_factor
    days_ago = int(weeks_back * 7 * (1 - progress))
    days_ago = random.randint(max(0, days_ago - 7), days_ago + 7)
    
    created_date = today - timedelta(days=days_ago)
    random_offset = random.randint(-5, 5)
    created_date += timedelta(days=random_offset)
    
    return created_date


def get_updated_date_for_issue(created_date: datetime, status: str, target_wi: float) -> datetime:
    """
    Генерирует дату обновления в зависимости от статуса и целевой загрузки
    """
    if status in ["Готово", "Done", "Closed"]:
        if target_wi > 1.2:
            # Перегруженный проект — задачи закрываются дольше
            days_after_created = random.randint(10, 45)
        elif target_wi < 0.6:
            # Недогруженный проект — закрываются быстро
            days_after_created = random.randint(1, 10)
        else:
            days_after_created = random.randint(3, 30)
        
        updated_date = created_date + timedelta(days=days_after_created)
        
    elif status in ["В работе", "In Progress", "Review", "На проверке"]:
        if target_wi > 1.2:
            days_after_created = random.randint(7, 60)
        else:
            days_after_created = random.randint(3, 30)
        updated_date = created_date + timedelta(days=days_after_created)
    else:
        days_after_created = random.randint(1, 14)
        updated_date = created_date + timedelta(days=days_after_created)
    
    if updated_date > datetime.now():
        updated_date = datetime.now()
    
    return updated_date


def update_issue_dates(db, issue_key: str, created_date: datetime, updated_date: datetime):
    """Обновляет даты задачи в БД"""
    db.execute(text("""
        UPDATE normalized.jira_issues 
        SET created_at = :created_at, 
            updated_at = :updated_at
        WHERE issue_key = :issue_key
    """), {
        "issue_key": issue_key,
        "created_at": created_date,
        "updated_at": updated_date
    })


def main():
    print("=" * 70)
    print("ОБНОВЛЕНИЕ ДАТ ЗАДАЧ В ЛОКАЛЬНОЙ БД (с учётом характеристик проектов)")
    print("=" * 70)
    print("\n⚠️  Это обновит ТОЛЬКО данные в твоей PostgreSQL БД")
    print("   Jira останется без изменений\n")
    
    db = SessionLocal()
    
    try:
        print_info("Получение списка проектов...")
        projects = get_projects(db)
        print_success(f"Найдено проектов: {len(projects)}")
        
        if not projects:
            print_error("Нет проектов в БД! Сначала синхронизируй данные из Jira.")
            return
        
        total_updated = 0
        summary = []
        
        for project_key in projects:
            print(f"\n📁 Проект: {project_key}")
            
            target_wi = get_target_workload(project_key)
            weeks_back = get_weeks_back_for_project(project_key)
            
            print(f"   Целевая загрузка: {target_wi*100:.0f}%")
            print(f"   Период: ~{weeks_back} недель назад")
            
            issues = get_project_issues(db, project_key)
            print(f"   Задач: {len(issues)}")
            
            if not issues:
                continue
            
            for i, issue in enumerate(issues, 1):
                created_date = get_random_date_for_issue(
                    issue_num=i, 
                    total_issues=len(issues),
                    weeks_back=weeks_back,
                    target_wi=target_wi
                )
                
                updated_date = get_updated_date_for_issue(
                    created_date, 
                    issue["status"],
                    target_wi
                )
                
                update_issue_dates(db, issue["key"], created_date, updated_date)
                total_updated += 1
                
                if i % 50 == 0:
                    print(f"   Обновлено: {i}/{len(issues)}")
            
            print_success(f"Проект {project_key}: обновлено {len(issues)} задач")
            summary.append({
                "project": project_key,
                "target_wi": target_wi,
                "weeks_back": weeks_back,
                "count": len(issues)
            })
        
        db.commit()
        
        print("\n" + "=" * 70)
        print("ИТОГИ")
        print("=" * 70)
        print_success(f"Всего обновлено задач: {total_updated}")
        
        print("\n📊 Сводка по проектам:")
        for s in summary:
            wi_status = "🔴 Перегруз" if s["target_wi"] > 1.2 else ("🟢 Норма" if s["target_wi"] > 0.7 else "🟠 Недогруз")
            print(f"   {s['project']}: {s['count']} задач, {wi_status} ({s['target_wi']*100:.0f}%), период ~{s['weeks_back']} нед.")
        
        print("\n📊 Проверка распределения дат по месяцам:")
        result = db.execute(text("""
            SELECT 
                EXTRACT(YEAR FROM created_at) as year,
                EXTRACT(MONTH FROM created_at) as month,
                COUNT(*) as count
            FROM normalized.jira_issues
            GROUP BY year, month
            ORDER BY year DESC, month DESC
            LIMIT 8
        """))
        
        for row in result:
            print(f"   {int(row[0])}-{int(row[1]):02d}: {row[2]} задач")
        
    except Exception as e:
        print_error(f"Ошибка: {e}")
        db.rollback()
        raise
    finally:
        db.close()
    
    print("\n" + "=" * 70)
    print("✅ ДАТЫ УСПЕШНО ОБНОВЛЕНЫ!")
    print("=" * 70)


if __name__ == "__main__":
    main()