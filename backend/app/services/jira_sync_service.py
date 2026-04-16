"""
Сервис для синхронизации задач из Jira в БД.
"""

import logging
from datetime import datetime
from sqlalchemy.orm import Session
from app.db.models import IntegrationToken, RawEvent, JiraIssue

logger = logging.getLogger(__name__)


class JiraSyncService:
    """Синхронизация данных из Jira в БД"""

    def __init__(self, db: Session):
        self.db = db

    def sync_project_issues(
        self,
        user_id: int,
        instance_name: str,
        project_key: str,
        jql: str = None
    ) -> dict:
        """Синхронизация с сохранением сырых данных"""
        
        # Получаем токен
        token = self.db.query(IntegrationToken).filter(
            IntegrationToken.user_id == user_id,
            IntegrationToken.instance_name == instance_name,
            IntegrationToken.provider == "jira"
        ).first()

        if not token:
            raise ValueError(f"Token not found for site {instance_name}")

        # Формируем JQL
        search_jql = f"project = {project_key}"
        
        # Прямой запрос
        import requests
        response = requests.get(
            f"https://api.atlassian.com/ex/jira/{token.instance_id}/rest/api/3/search/jql",
            headers={"Authorization": f"Bearer {token.access_token}"},
            params={
                "jql": search_jql,
                "startAt": 0,
                "maxResults": 50,
                "fields": "*all"
            },
            timeout=30
        )
        
        if response.status_code != 200:
            raise Exception(f"API error: {response.status_code} - {response.text}")
        
        data = response.json()
        issues = data.get("issues", [])
        
        created_count = 0
        updated_count = 0
        
        for issue in issues:
            issue_key = issue.get("key")
            if not issue_key:
                continue
            
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
            
            # 2. Проверяем, существует ли уже нормализованная задача
            existing = self.db.query(JiraIssue).filter(
                JiraIssue.issue_key == issue_key
            ).first()
            
            fields = issue.get("fields", {})
            
            # Извлекаем Story Points (с проверкой на пустые значения)
            story_points = None
            for field_name in ["customfield_10002", "customfield_10016"]:
                if field_name in fields:
                    val = fields.get(field_name)
                    # Проверяем, что значение не пустое и не список
                    if val is not None and not isinstance(val, list):
                        story_points = float(val) if isinstance(val, (int, float)) else None
                        break
            
            assignee = fields.get("assignee")
            assignee_account_id = assignee.get("accountId") if assignee else None
            assignee_name = assignee.get("displayName") if assignee else None
            
            priority = fields.get("priority")
            priority_name = priority.get("name") if priority else None
            
            issuetype = fields.get("issuetype")
            issue_type_name = issuetype.get("name") if issuetype else None
            
            status = fields.get("status")
            status_name = status.get("name") if status else None
            status_category = status.get("statusCategory", {}).get("name") if status else None
            
            if existing:
                # Обновляем существующую задачу
                existing.summary = fields.get("summary")
                existing.status = status_name
                existing.status_category = status_category
                existing.assignee_account_id = assignee_account_id
                existing.assignee_name = assignee_name
                existing.priority = priority_name
                existing.issue_type = issue_type_name
                if story_points is not None:
                    existing.story_points = story_points
                existing.due_date = fields.get("duedate")
                existing.updated_at = fields.get("updated")
                existing.last_synced_at = datetime.utcnow()
                updated_count += 1
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
                    priority=priority_name,
                    issue_type=issue_type_name,
                    story_points=story_points,
                    due_date=fields.get("duedate"),
                    created_at=fields.get("created"),
                    updated_at=fields.get("updated"),
                    last_synced_at=datetime.utcnow()
                )
                self.db.add(new_issue)
                created_count += 1
        
        self.db.commit()
        
        return {
            "created": created_count,
            "updated": updated_count,
            "total": created_count + updated_count,
            "project_key": project_key,
            "instance_name": instance_name
        }