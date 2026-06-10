# app/services/ai/insight_service.py
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from typing import List, Optional
from app.db.models import JiraIssue, Project, UserProject


class AIInsightService:

    def __init__(self, db, ai_provider):
        self.db = db
        self.ai_provider = ai_provider

    async def build_insights(self, user_id: Optional[int] = None, project_keys: Optional[List[str]] = None):
        """
        Строит AI-инсайты с привязкой к проектам.
        
        Args:
            user_id: ID пользователя (фильтрует проекты по UserProject)
            project_keys: Список project_key для фильтрации
        
        Returns:
            List[dict]: Список инсайтов
        """
        
        # ============================================================
        # ФИЛЬТРАЦИЯ ПРОЕКТОВ (приоритет: project_keys > user_id)
        # ============================================================
        
        final_project_keys = []
        
        if project_keys:
            # Если переданы project_keys — используем их
            final_project_keys = project_keys
        elif user_id:
            # Если нет project_keys, но есть user_id — получаем проекты пользователя
            user_projects = self.db.query(Project).join(
                UserProject, UserProject.project_id == Project.id
            ).filter(
                UserProject.user_id == user_id,
                Project.is_active == True
            ).all()
            
            final_project_keys = [p.jira_project_key for p in user_projects if p.jira_project_key]
        
        # Если нет проектов — возвращаем пустой список
        if not final_project_keys:
            return []
        
        # Получаем проекты из JiraIssue (только те, что в final_project_keys)
        projects_query = self.db.query(JiraIssue.project_key).filter(
            JiraIssue.project_key.in_(final_project_keys),
            JiraIssue.is_deleted == False
        ).distinct()
        
        projects = projects_query.all()

        if not projects:
            return []

        # Получаем названия проектов из core.projects
        project_names = {}
        projects_from_db = self.db.query(Project).filter(
            Project.jira_project_key.in_(final_project_keys)
        ).all()
        for proj in projects_from_db:
            project_names[proj.jira_project_key] = proj.name
        
        projects_data = []

        for (project_key,) in projects:
            # Собираем статистику по проекту
            issues = self.db.query(JiraIssue).filter(
                JiraIssue.project_key == project_key,
                JiraIssue.is_deleted == False
            ).all()
            
            if not issues:
                continue
            
            # Агрегируем данные
            open_issues = [i for i in issues if i.status not in ['Done', 'Closed', 'Готово']]
            closed_issues = [i for i in issues if i.status in ['Done', 'Closed', 'Готово']]
            bugs = [i for i in issues if i.issue_type and i.issue_type.lower() in ['bug', 'defect', 'error']]
            overdue = [i for i in open_issues if i.due_date and i.due_date < datetime.utcnow()]
            
            # Считаем Story Points
            total_sp = sum(i.story_points or 0 for i in open_issues)
            completed_sp = sum(i.story_points or 0 for i in closed_issues)
            
            # Completion rate
            if total_sp == 0:
                completion_rate = 100.0 if completed_sp > 0 else 0.0
            else:
                completion_rate = round(completed_sp / (total_sp + completed_sp) * 100, 1)
            
            assignees = {}
            for issue in open_issues:
                assignee = issue.assignee_name or issue.assignee_account_id or 'Не назначен'
                if assignee not in assignees:
                    assignees[assignee] = {'count': 0, 'sp': 0, 'bugs': 0}
                assignees[assignee]['count'] += 1
                assignees[assignee]['sp'] += issue.story_points or 0
                if issue.issue_type and issue.issue_type.lower() in ['bug', 'defect', 'error']:
                    assignees[assignee]['bugs'] += 1
            
            # Формируем данные для проекта
            project_info = {
                "project_key": project_key,
                "project_name": project_names.get(project_key, project_key),
                "total_issues": len(issues),
                "open_issues": len(open_issues),
                "closed_issues": len(closed_issues),
                "bugs_count": len(bugs),
                "overdue_count": len(overdue),
                "total_story_points": total_sp,
                "completed_story_points": completed_sp,
                "completion_rate": completion_rate,
                "assignees": assignees,
                "statuses": list(set(i.status for i in issues if i.status)),
                "issue_types": list(set(i.issue_type for i in issues if i.issue_type))
            }
            
            projects_data.append(project_info)
        
        # Генерируем инсайты для каждого проекта
        all_insights = []
        insight_id = 1
        
        for project_data in projects_data:
            project_insights = await self._analyze_project(project_data)
            for insight in project_insights:
                insight['id'] = insight_id
                insight_id += 1
                all_insights.append(insight)
        
        # Сортируем по приоритету (error > warning > success)
        priority = {'error': 0, 'warning': 1, 'success': 2}
        all_insights.sort(key=lambda x: priority.get(x.get('type', 'success'), 3))
        
        # Опционально: можно запросить у LLM дополнительные инсайты
        if projects_data and self.ai_provider:
            try:
                llm_insights = await self.ai_provider.generate_insights(projects_data)
                for insight in llm_insights:
                    insight['id'] = insight_id
                    insight_id += 1
                    all_insights.append(insight)
            except Exception as e:
                print(f"[WARNING] LLM insights failed: {e}")
        
        return all_insights
    
    async def _analyze_project(self, project_data: dict) -> list:
        """Анализирует один проект и возвращает инсайты."""
        insights = []
        project_key = project_data['project_key']
        project_name = project_data['project_name']
        
        # 1. Просроченные задачи
        if project_data['overdue_count'] > 0:
            insights.append({
                'type': 'error',
                'text': f"{project_name} ({project_key}): {project_data['overdue_count']} просроченных задач",
                'recommendation': f"Срочно пересмотреть дедлайны в {project_name}"
            })
        
        # 2. Много багов
        if project_data['bugs_count'] > 5:
            insights.append({
                'type': 'error',
                'text': f"{project_name} ({project_key}): высокий уровень багов ({project_data['bugs_count']})",
                'recommendation': f"Выделить спринт на технический долг в {project_name}"
            })
        elif project_data['bugs_count'] > 0:
            insights.append({
                'type': 'warning',
                'text': f"{project_name} ({project_key}): {project_data['bugs_count']} активных багов",
                'recommendation': f"Включить баги в план работ {project_name}"
            })
        
        # 3. Низкий completion rate
        if project_data['completion_rate'] < 50 and project_data['total_story_points'] > 0:
            insights.append({
                'type': 'warning',
                'text': f"{project_name} ({project_key}): низкая скорость закрытия ({project_data['completion_rate']}%)",
                'recommendation': f"Проверить загрузку команды {project_name}"
            })
        
        # 4. Перегрузка конкретных сотрудников
        for assignee, data in project_data['assignees'].items():
            if data['count'] > 10:
                insights.append({
                    'type': 'warning',
                    'text': f"{project_name} ({project_key}): {assignee} перегружен ({data['count']} задач)",
                    'recommendation': f"Перераспределить задачи в {project_name}"
                })
            
            if data['bugs'] > 3:
                insights.append({
                    'type': 'warning',
                    'text': f"{project_name} ({project_key}): {assignee} назначен на {data['bugs']} багов",
                    'recommendation': f"Рассмотреть код-ревью для {assignee} в {project_name}"
                })
        
        # 5. Положительный инсайт - хороший прогресс
        if (project_data['completion_rate'] >= 80 and 
            project_data['total_issues'] > 0 and
            project_data['bugs_count'] == 0):
            insights.append({
                'type': 'success',
                'text': f"{project_name} ({project_key}): ситуация стабильная ({project_data['completion_rate']}% готово)",
                'recommendation': f"Можно подключать новые задачи в {project_name}"
            })
        
        return insights