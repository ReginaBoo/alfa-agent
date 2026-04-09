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
        
        for issue in issues:
            # 1. СОХРАНЯЕМ СЫРЫЕ ДАННЫЕ в raw_events
            raw_event = RawEvent(
                source="jira",
                event_type="issue",
                external_id=issue.get("id"),
                project_integration_id=None,
                payload=issue,  # полный JSON ответа
                timestamp=datetime.utcnow()
            )
            self.db.add(raw_event)
            
            # 2. Проверяем, существует ли уже нормализованная задача
            existing = self.db.query(JiraIssue).filter(
                JiraIssue.issue_key == issue.get("key")
            ).first()
            
            if not existing:
                # 3. НОРМАЛИЗУЕМ и сохраняем в jira_issues
                fields = issue.get("fields", {})
                
                # Извлекаем Story Points
                story_points = None
                for field_name in ["customfield_10002", "customfield_10016"]:
                    if field_name in fields:
                        story_points = fields.get(field_name)
                        break
                
                new_issue = JiraIssue(
                    issue_key=issue.get("key"),
                    project_key=project_key,
                    summary=fields.get("summary"),
                    status=fields.get("status", {}).get("name"),
                    status_category=fields.get("status", {}).get("statusCategory", {}).get("name"),
                    assignee_account_id=fields.get("assignee", {}).get("accountId") if fields.get("assignee") else None,
                    assignee_name=fields.get("assignee", {}).get("displayName") if fields.get("assignee") else None,
                    priority=fields.get("priority", {}).get("name") if fields.get("priority") else None,
                    issue_type=fields.get("issuetype", {}).get("name") if fields.get("issuetype") else None,
                    story_points=story_points,
                    due_date=fields.get("duedate"),  # ДОБАВИТЬ ЭТУ СТРОКУ
                    created_at=fields.get("created"),  # ИЗМЕНИТЬ: использовать дату из Jira
                    updated_at=fields.get("updated"),  # ИЗМЕНИТЬ: использовать дату из Jira
                    last_synced_at=datetime.utcnow()
                )
                self.db.add(new_issue)
                created_count += 1
        
        self.db.commit()
        
        return {
            "created": created_count,
            "updated": 0,
            "total": created_count,
            "project_key": project_key,
            "instance_name": instance_name
        }