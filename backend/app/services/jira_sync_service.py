"""
Сервис для синхронизации задач из Jira в БД.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.db.models import IntegrationToken, RawEvent, JiraIssue
from app.db.models.normalized import IssueChangelog, ProjectStatusMapping
from app.services.status_mapping_service import StatusMappingService

logger = logging.getLogger(__name__)


class JiraSyncService:
    """Синхронизация данных из Jira в БД"""

    def __init__(self, db: Session):
        self.db = db

    def _extract_story_points(self, fields: dict) -> Optional[float]:
        """Извлекает Story Points из полей задачи"""
        # Стандартные поля для Story Points в Jira Cloud
        story_points_fields = [
            "customfield_10016",  # Чаще всего используется
            "customfield_10002",  # Альтернативный
            "customfield_10024",  # Ещё один вариант
            "customfield_10026",
            "customfield_10030"
        ]
        
        for field_name in story_points_fields:
            if field_name in fields:
                val = fields.get(field_name)
                if val is not None and not isinstance(val, list) and not isinstance(val, dict):
                    try:
                        return float(val) if isinstance(val, (int, float)) else None
                    except (ValueError, TypeError):
                        continue
        return None

    def _extract_timetracking(self, fields: dict) -> Dict[str, Optional[float]]:
        """Извлекает временные оценки из задачи"""
        timetracking = fields.get('timetracking', {})
        
        original_estimate = None
        time_spent = None
        remaining_estimate = None
        
        # Пробуем разные форматы
        if timetracking.get('originalEstimateSeconds'):
            original_estimate = timetracking['originalEstimateSeconds'] / 3600  # в часы
        elif fields.get('timeoriginalestimate'):
            original_estimate = fields['timeoriginalestimate'] / 3600
        
        if timetracking.get('timeSpentSeconds'):
            time_spent = timetracking['timeSpentSeconds'] / 3600
        elif fields.get('aggregatetimespent'):
            time_spent = fields['aggregatetimespent'] / 3600
        
        if timetracking.get('remainingEstimateSeconds'):
            remaining_estimate = timetracking['remainingEstimateSeconds'] / 3600
        
        return {
            'original_estimate': original_estimate,
            'time_spent': time_spent,
            'remaining_estimate': remaining_estimate
        }
    
    def _get_closed_at_from_changelog(
        self,
        issue_key: str,
        closed_statuses: list
    ) -> Optional[datetime]:
        """
        Определяет дату закрытия задачи по changelog.
        Ищет первый переход в закрытый статус.
        """
        closing_event = self.db.query(IssueChangelog).filter(
            IssueChangelog.issue_key == issue_key,
            IssueChangelog.field_name == 'status',
            IssueChangelog.to_value.in_(closed_statuses)
        ).order_by(IssueChangelog.changed_at.asc()).first()
        
        if closing_event:
            return closing_event.changed_at
        
        return None


    def _get_closed_statuses_for_project(self, project_key: str) -> list:
        """
        Получает закрытые статусы для проекта из ProjectStatusMapping
        """
        mappings = self.db.query(ProjectStatusMapping).filter(
            ProjectStatusMapping.project_key == project_key,
            ProjectStatusMapping.is_closed == True
        ).all()
        
        if mappings:
            return [m.status_name for m in mappings]
        
        # Fallback
        return ['Done', 'Closed', 'Resolved', 'Готово', 'Выполнено', 'Закрыто']



    def _sync_project_statuses_if_needed(
        self,
        project_key: str,
        token: IntegrationToken
    ) -> bool:
        """
        Синхронизирует статусы проекта, если они ещё не синхронизированы
        или устарели (старше 7 дней)
        """
        from app.jira.client import JiraClient
        import asyncio
        
        # Проверяем, есть ли уже статусы в БД
        existing_mappings = self.db.query(ProjectStatusMapping).filter(
            ProjectStatusMapping.project_key == project_key
        ).first()
        
        # Если нет статусов или они устарели (> 7 дней)
        need_sync = False
        if not existing_mappings:
            need_sync = True
            logger.info(f"No status mappings found for {project_key}, will sync")
        elif existing_mappings.last_synced_at:
            days_since_sync = (datetime.utcnow() - existing_mappings.last_synced_at).days
            if days_since_sync > 7:
                need_sync = True
                logger.info(f"Status mappings for {project_key} are {days_since_sync} days old, refreshing")
        
        if need_sync:
            try:
                # Используем async клиент
                jira_client = JiraClient(token.access_token, token.refresh_token)
                
                # Синхронизируем статусы (используем asyncio.run для синхронного контекста)
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    mappings = loop.run_until_complete(
                        StatusMappingService.sync_project_statuses(
                            db=self.db,
                            project_key=project_key,
                            jira_client=jira_client,
                            synced_by_account_id=token.provider_user_id
                        )
                    )
                    logger.info(f"Synced {len(mappings)} statuses for project {project_key}")
                finally:
                    loop.close()
                
                return True
            except Exception as e:
                logger.error(f"Failed to sync statuses for {project_key}: {e}")
                return False
        
        return False

    def sync_project_issues(
        self,
        user_id: int,
        instance_name: str,
        project_key: str,
        jql: str = None,
        sync_statuses: bool = True
    ) -> dict:
        """
        Синхронизация с сохранением сырых данных и пагинацией
        """
        # Получаем токен
        token = self.db.query(IntegrationToken).filter(
            IntegrationToken.user_id == user_id,
            IntegrationToken.instance_name == instance_name,
            IntegrationToken.provider == "jira"
        ).first()
        
        if not token:
            raise ValueError(f"Token not found for site {instance_name}")
        
        # 1. СИНХРОНИЗИРУЕМ СТАТУСЫ ПРОЕКТА (если нужно)
        if sync_statuses:
            self._sync_project_statuses_if_needed(project_key, token)
        
        # Формируем JQL
        search_jql = jql or f"project = {project_key}"
        
        # Пагинация
        start_at = 0
        max_results = 100
        total_issues = 0
        
        created_count = 0
        updated_count = 0
        changelog_added = 0
        all_actual_issue_keys = set()
        # Получаем закрытые статусы для проекта
        closed_statuses = self._get_closed_statuses_for_project(project_key)
        from datetime import datetime, timezone

        sync_started_at = datetime.now(timezone.utc)
        while True:
            logger.info(f"Fetching issues for {project_key}, start_at={start_at}")
            
            # Прямой запрос с пагинацией
            import requests
            response = requests.get(
                f"https://api.atlassian.com/ex/jira/{token.instance_id}/rest/api/3/search/jql",
                headers={"Authorization": f"Bearer {token.access_token}"},
                params={
                    "jql": search_jql,
                    "startAt": start_at,
                    "maxResults": max_results,
                    "fields": "*all",
                    "expand": "changelog,transitions"
                },
                timeout=30
            )
            
            if response.status_code != 200:
                raise Exception(f"API error: {response.status_code} - {response.text}")
            
            data = response.json()
            issues = data.get("issues", [])
            total = data.get("total", 0)
            
            logger.info(f"Sample issue keys: {[i['key'] for i in issues[:3]]}")

            if issues:
                logger.info(f"First issue has changelog: {'changelog' in issues[0]}")
                if 'changelog' in issues[0]:
                    logger.info(f"Changelog values count: {len(issues[0].get('changelog', {}).get('values', []))}")

            if not issues:
                logger.info(f"No more issues to fetch for {project_key}")
                break
            
            logger.info(f"Fetched {len(issues)} issues (total: {total})")
            
            # Обрабатываем каждую задачу
            for issue in issues:
                issue_key = issue.get("key")

                if not issue_key:
                    continue

                all_actual_issue_keys.add(issue_key)
                
                total_issues += 1
                fields = issue.get("fields", {})
                
                # 1. СОХРАНЯЕМ СЫРЫЕ ДАННЫЕ в raw_events
                raw_event = RawEvent(
                    source="jira",
                    event_type="issue",
                    external_id=issue.get("id"),
                    project_integration_id=None,
                    payload=issue,
                    timestamp=datetime.utcnow()
                )
                self.db.add(raw_event)
                
                # 2. СОХРАНЯЕМ CHANGELOG (ВСЕ изменения, а не только статусы)
                changelog_data = issue.get('changelog', {})
                histories = (
                    changelog_data.get('values')
                    or changelog_data.get('histories')
                    or []
                )

                for history in histories:
                    changed_at = history.get('created')
                    author = history.get('author', {})
                    author_account_id = author.get('accountId') if author else None
                    
                    for item in history.get('items', []):
                        field_name = item.get('field')
                        from_value = item.get('fromString') or item.get('from')
                        to_value = item.get('toString') or item.get('to')
                        
                        # Проверяем, есть ли уже такая запись
                        existing_changelog = self.db.query(IssueChangelog).filter(
                            IssueChangelog.issue_key == issue_key,
                            IssueChangelog.field_name == field_name,
                            IssueChangelog.changed_at == changed_at,
                            IssueChangelog.from_value == from_value,
                            IssueChangelog.to_value == to_value
                        ).first()
                        
                        if not existing_changelog:
                            changelog_entry = IssueChangelog(
                                issue_key=issue_key,
                                field_name=field_name,
                                from_value=from_value,
                                to_value=to_value,
                                changed_at=changed_at,
                                author_account_id=author_account_id
                            )
                            self.db.add(changelog_entry)
                            changelog_added += 1
                
                # 3. Извлекаем данные из полей
                story_points = self._extract_story_points(fields)
                timetracking = self._extract_timetracking(fields)
                
                assignee = fields.get("assignee")
                assignee_account_id = assignee.get("accountId") if assignee else None
                assignee_name = assignee.get("displayName") if assignee else None
                
                reporter = fields.get("reporter")
                reporter_account_id = reporter.get("accountId") if reporter else None
                
                priority = fields.get("priority")
                priority_name = priority.get("name") if priority else None
                
                issuetype = fields.get("issuetype")
                issue_type_name = issuetype.get("name") if issuetype else None
                
                status = fields.get("status")
                status_name = status.get("name") if status else None
                status_category = status.get("statusCategory", {}).get("name") if status else None
                
                # ========== ОПРЕДЕЛЯЕМ closed_at ==========
                closed_at = None
                
                # Если текущий статус закрытый
                if status_name and status_name in closed_statuses:
                    closed_at = self._get_closed_at_from_changelog(
                        issue_key=issue_key,
                        closed_statuses=closed_statuses
                    )
                else:
                    # Ищем в changelog первый переход в закрытый статус
                    closing_event = self.db.query(IssueChangelog).filter(
                        IssueChangelog.issue_key == issue_key,
                        IssueChangelog.field_name == 'status',
                        IssueChangelog.to_value.in_(closed_statuses)
                    ).order_by(IssueChangelog.changed_at.asc()).first()
                    
                    if closing_event:
                        closed_at = closing_event.changed_at
                # ==========================================
                
                # 4. Проверяем, существует ли уже нормализованная задача
                existing = self.db.query(JiraIssue).filter(
                    JiraIssue.issue_key == issue_key
                ).first()
                
                if existing:
                    # Обновляем существующую задачу
                    existing.summary = fields.get("summary")
                    existing.status = status_name
                    existing.status_category = status_category
                    existing.assignee_account_id = assignee_account_id
                    existing.assignee_name = assignee_name
                    existing.reporter_account_id = reporter_account_id
                    existing.priority = priority_name
                    existing.issue_type = issue_type_name
                    if story_points is not None:
                        existing.story_points = story_points
                    existing.due_date = fields.get("duedate")
                    existing.updated_at = fields.get("updated")
                    existing.last_synced_at = datetime.utcnow()
                    existing.original_estimate = timetracking['original_estimate']
                    existing.time_spent = timetracking['time_spent']
                    existing.remaining_estimate = timetracking['remaining_estimate']
                    existing.closed_at = closed_at  # <-- ДОБАВЛЕНО
                    updated_count += 1
                    existing.is_deleted = False
                else:
                    # Создаём новую задачу
                    new_issue = JiraIssue(
                        issue_key=issue_key,
                        project_key=project_key,
                        summary=fields.get("summary"),
                        status=status_name,
                        status_category=status_category,
                        assignee_account_id=assignee_account_id,
                        assignee_name=assignee_name,
                        reporter_account_id=reporter_account_id,
                        priority=priority_name,
                        issue_type=issue_type_name,
                        story_points=story_points,
                        due_date=fields.get("duedate"),
                        created_at=fields.get("created"),
                        updated_at=fields.get("updated"),
                        last_synced_at=datetime.utcnow(),
                        original_estimate=timetracking['original_estimate'],
                        time_spent=timetracking['time_spent'],
                        remaining_estimate=timetracking['remaining_estimate'],
                        closed_at=closed_at,  # <-- ДОБАВЛЕНО
                        is_deleted=False
                    )
                    self.db.add(new_issue)
                    created_count += 1
            
            # Проверяем, нужно ли продолжать
            start_at += max_results
            if start_at >= total:
                break
        # Все issue_key, которые сейчас существуют в Jira
        actual_issue_keys = all_actual_issue_keys

        # Все задачи проекта в БД
        db_issues = self.db.query(JiraIssue).filter(
            JiraIssue.project_key == project_key
        ).all()

        # Если задача есть в БД, но её нет в Jira — помечаем удалённой
        for db_issue in db_issues:
            if db_issue.issue_key not in actual_issue_keys:
                db_issue.is_deleted = True
                # Коммитим после каждой пачки
        self.db.commit()

        logger.info(f"Sync completed for {project_key}: "
                    f"created={created_count}, updated={updated_count}, "
                    f"changelog_entries={changelog_added}")
        
        return {
            "created": created_count,
            "updated": updated_count,
            "total": total_issues,
            "changelog_added": changelog_added,
            "project_key": project_key,
            "instance_name": instance_name
        }
    
    def get_project_statuses(self, project_key: str) -> list:
        """
        Возвращает синхронизированные статусы проекта
        """
        mappings = self.db.query(ProjectStatusMapping).filter(
            ProjectStatusMapping.project_key == project_key
        ).all()
        
        return [
            {
                "status_name": m.status_name,
                "is_open": m.is_open,
                "is_in_progress": m.is_in_progress,
                "is_closed": m.is_closed,
                "jira_category": m.jira_category,
                "last_synced_at": m.last_synced_at.isoformat() if m.last_synced_at else None
            }
            for m in mappings
        ]