from sqlalchemy.orm import Session
from app.db.models import JiraIssue


class AIInsightService:

    def __init__(self, db, ai_provider):
        self.db = db
        self.ai_provider = ai_provider

    async def build_insights(self):

        issues = self.db.query(JiraIssue).all()

        projects_data = []

        for issue in issues:
            projects_data.append({
                "project": issue.project_key,
                "status": issue.status,
                "assignee": issue.assignee_name,
                "story_points": issue.story_points,
                "is_deleted": issue.is_deleted
            })

        return await self.ai_provider.generate_insights(projects_data)