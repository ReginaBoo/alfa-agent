#!/usr/bin/env python3
"""
Скрипт для ручной синхронизации проектов и задач из Jira.
Запуск:
  - Локально: python sync_jira.py --user-id 1 --instance my-jira --project KEY
  - В Docker: docker compose run --rm \
    -e DATABASE_URL="postgresql://postgres:postgres@db:5432/app_db" \
    backend python scripts/sync_jira.py --user-id 1 --instance reginaboo --project DEV
"""

import argparse
import logging
import os
import sys
from datetime import datetime

# Добавляем корень проекта в PATH для импортов
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Импорт моделей и сервисов
from app.db.models import IntegrationToken
from app.services.jira_sync_service import JiraSyncService
from app.services.project_sync_service import sync_projects_from_jira

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("sync_jira")


def get_db_session(database_url: str):
    """Создаёт сессию SQLAlchemy"""
    engine = create_engine(database_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return SessionLocal()


def parse_args():
    parser = argparse.ArgumentParser(description="Sync Jira projects and issues to DB")
    parser.add_argument("--user-id", type=int, required=True, help="ID пользователя в системе")
    parser.add_argument("--instance", type=str, required=True, help="Имя Jira-инстанса (instance_name из токена)")
    parser.add_argument("--project", type=str, required=True, help="Ключ проекта Jira (например, DEV)")
    parser.add_argument("--jql", type=str, default=None, help="Опциональный JQL-фильтр для задач")
    parser.add_argument("--no-statuses", action="store_true", help="Не синхронизировать статусы проекта")
    parser.add_argument("--db-url", type=str, default=None, help="Override DATABASE_URL (для тестов)")
    return parser.parse_args()


def main():
    args = parse_args()
    
    # Получаем URL БД
    db_url = args.db_url or os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL not set. Use --db-url or set env variable.")
        sys.exit(1)
    
    logger.info(f"Starting sync: user={args.user_id}, instance={args.instance}, project={args.project}")
    
    db = None
    try:
        # 1. Инициализация БД
        db = get_db_session(db_url)
        
        # 2. Проверка наличия токена
        token = db.query(IntegrationToken).filter(
            IntegrationToken.user_id == args.user_id,
            IntegrationToken.instance_name == args.instance,
            IntegrationToken.provider == "jira"
        ).first()
        
        if not token:
            logger.error(f"Jira token not found for user={args.user_id}, instance={args.instance}")
            sys.exit(2)
        
        logger.info(f"✓ Token found: instance_id={token.instance_id}, user={token.provider_user_id}")
        
        # 3. Синхронизация ПРОЕКТОВ
        logger.info("Syncing projects...")
        projects_result = sync_projects_from_jira(
            db=db,
            user_id=args.user_id,
            instance_name=args.instance,
            sync_statuses=not args.no_statuses
        )
        logger.info(f"✓ Projects: {projects_result['created']} created, {projects_result['updated']} updated, "
                    f"{projects_result['statuses_synced']} statuses synced")
        
        # 4. Синхронизация ЗАДАЧ
        logger.info("Syncing issues...")
        sync_service = JiraSyncService(db=db)
        issues_result = sync_service.sync_project_issues(
            user_id=args.user_id,
            instance_name=args.instance,
            project_key=args.project,
            jql=args.jql,
            sync_statuses=not args.no_statuses
        )
        logger.info(f"✓ Issues: {issues_result['created']} created, {issues_result['updated']} updated, "
                    f"{issues_result['changelog_added']} changelog entries, total={issues_result['total']}")
        
        # 5. Финальный коммит (если сервисы не закоммитили внутри)
        db.commit()
        
        logger.info("Sync completed successfully!")
        return 0
        
    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        if db:
            db.rollback()
        return 130
    except Exception as e:
        logger.exception(f"Sync failed: {e}")
        if db:
            db.rollback()
        return 1
    finally:
        if db:
            db.close()


if __name__ == "__main__":
    sys.exit(main() or 0)