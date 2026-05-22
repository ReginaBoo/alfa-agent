#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_health_dates.py

Обновляет даты создания и обновления задач HEALTH в локальной БД
для реалистичного распределения по времени.
"""

import sys
import os
import random
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.db.session import SessionLocal


def print_info(msg: str): print(f"INFO: {msg}")
def print_success(msg: str): print(f"✅ {msg}")


def main():
    print("=" * 70)
    print("ОБНОВЛЕНИЕ ДАТ ДЛЯ ПРОЕКТА HEALTH")
    print("=" * 70)
    
    db = SessionLocal()
    
    try:
        # Получаем все задачи HEALTH
        issues = db.execute(text("""
            SELECT issue_key, status 
            FROM normalized.jira_issues 
            WHERE project_key = 'HEALTH'
        """)).fetchall()
        
        print(f"📋 Найдено задач: {len(issues)}")
        
        today = datetime.now()
        total_updated = 0
        
        for issue_key, status in issues:
            # Генерируем дату создания (1-4 недели назад)
            days_ago = random.randint(7, 28)
            created_date = today - timedelta(days=days_ago)
            
            # Генерируем дату обновления (позже создания)
            if status in ["Готово", "Done", "Closed"]:
                days_after = random.randint(3, days_ago - 1)
                updated_date = created_date + timedelta(days=days_after)
            else:
                updated_date = created_date + timedelta(days=random.randint(1, 7))
                if updated_date > today:
                    updated_date = today
            
            # Обновляем в БД
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
            total_updated += 1
            
            if total_updated % 20 == 0:
                print(f"   Обновлено: {total_updated}/{len(issues)}")
        
        db.commit()
        print_success(f"Обновлено задач: {total_updated}")
        
        # Проверяем распределение дат
        result = db.execute(text("""
            SELECT 
                EXTRACT(YEAR FROM created_at) as year,
                EXTRACT(MONTH FROM created_at) as month,
                COUNT(*) as count
            FROM normalized.jira_issues
            WHERE project_key = 'HEALTH'
            GROUP BY year, month
            ORDER BY year DESC, month DESC
        """)).fetchall()
        
        print("\n📊 Распределение дат:")
        for row in result:
            print(f"   {int(row[0])}-{int(row[1]):02d}: {row[2]} задач")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        db.rollback()
        raise
    finally:
        db.close()
    
    print("\n" + "=" * 70)
    print("✅ ДАТЫ УСПЕШНО ОБНОВЛЕНЫ!")
    print("=" * 70)


if __name__ == "__main__":
    main()