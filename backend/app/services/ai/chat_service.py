"""
Сервис для умного чата с AI и доступом к БД
"""
import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime

from app.services.ai.providers.alphabank_provider import AlphaBankProvider
from app.core.config import settings

logger = logging.getLogger(__name__)


# Разрешённые таблицы для SELECT запросов
ALLOWED_TABLES = {
    "identity.users",
    "core.projects",
    "core.user_projects",
    "normalized.jira_issues",
    "normalized.issue_changelog",
    "normalized.project_status_mappings",
    "normalized.github_issues",
    "normalized.github_commits",
    "normalized.github_pull_requests",
}

# Запрещённые ключевые слова (DML/DDL)
FORBIDDEN_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE", 
    "ALTER", "CREATE", "MERGE", "EXEC", "EXECUTE"
]


class ChatService:
    """Сервис для обработки чат-запросов с AI"""
    
    def __init__(self, db: Session, ai_provider: AlphaBankProvider):
        self.db = db
        self.ai_provider = ai_provider
        self.session_id: Optional[str] = None
        self.history: List[Dict[str, str]] = []
    
    def set_session(self, session_id: str, history: Optional[List[Dict[str, str]]] = None):
        """Устанавливает сессию чата"""
        self.session_id = session_id
        self.history = history or []
    
    async def process_message(self, message: str) -> Dict[str, Any]:
        """
        Обрабатывает сообщение пользователя и возвращает ответ AI
        
        Args:
            message: Текст сообщения пользователя
            
        Returns:
            Dict с ответом AI и метаданными
        """
        # Добавляем сообщение пользователя в историю
        self.history.append({"role": "user", "content": message})
        
        # Формируем системный промпт
        system_prompt = self._build_system_prompt()
        
        # Формируем messages для AI
        messages = [
            {"role": "system", "content": system_prompt},
            *self.history[-10:]  # Последние 10 сообщений для контекста
        ]
        
        # Получаем ответ от AI
        try:
            ai_response = await self.ai_provider.chat_completions(messages)
        except Exception as e:
            logger.error(f"AI chat completion failed: {e}")
            return {
                "answer": "Извините, произошла ошибка при обработке вашего запроса.",
                "session_id": self.session_id,
                "metadata": {
                    "error": str(e),
                    "sql_queries": [],
                    "tool_calls": []
                }
            }
        
        # Парсим ответ AI (может содержать tool calls)
        answer, tool_calls, sql_queries = await self._parse_ai_response(ai_response)
        
        # Добавляем ответ AI в историю
        self.history.append({"role": "assistant", "content": answer})
        
        return {
            "answer": answer,
            "session_id": self.session_id,
            "metadata": {
                "sql_queries": sql_queries,
                "tool_calls": tool_calls
            }
        }
    
    def _build_system_prompt(self) -> str:
        """Формирует системный промпт для AI"""
        return """Вы — умный помощник для аналитики разработки Alpha Agent.
        
Ваша задача:
1. Отвечать на вопросы о проектах, задачах, загрузке команды
2. Использовать доступные инструменты для получения данных из БД
3. Отвечать понятным языком, без технического жаргона

Доступные инструменты:
1. execute_sql(sql: str) — выполнить SELECT запрос к БД
   - Только SELECT запросы!
   - Разрешённые таблицы:
     * identity.users — пользователи
     * core.projects — проекты
     * core.user_projects — связи пользователей и проектов
     * normalized.jira_issues — задачи Jira
     * normalized.issue_changelog — история изменений задач
     * normalized.github_issues — GitHub Issues
     * normalized.github_commits — GitHub Commits
     * normalized.github_pull_requests — GitHub Pull Requests
   - Максимум 100 строк в ответе
   - Используйте LIMIT 100

2. get_project_metrics(project_key: str) — получить метрики проекта
   - Возвращает: workload, SLA, health score

3. get_user_workload(user_id: str) — получить загрузку пользователя
   - Возвращает: количество задач, story points

Примеры вопросов и ответов:

Пользователь: "Сколько задач у Ивана?"
Вызови: execute_sql("SELECT assignee_name, COUNT(*) as task_count FROM normalized.jira_issues WHERE assignee_name = 'Иван' AND status NOT IN ('Done', 'Closed') GROUP BY assignee_name LIMIT 100")
Ответь: "У Ивана X активных задач"

Пользователь: "Какой проект самый проблемный?"
Вызови: execute_sql("SELECT project_key, COUNT(*) as bug_count FROM normalized.jira_issues WHERE issue_type = 'Bug' AND status NOT IN ('Done', 'Closed') GROUP BY project_key ORDER BY bug_count DESC LIMIT 10")
Ответь: "Самый проблемный проект — {project_key} с {count} багами"

Правила:
- Всегда выполняй SQL запросы перед ответом
- Если данные получены — опиши их понятным языком
- Не выдумывай данные
- Если не уверен — спроси уточняющий вопрос
- Ограничь ответ 2-3 предложениями"""

    async def _parse_ai_response(self, ai_response: str) -> Tuple[str, List[str], List[str]]:
        """
        Парсит ответ AI и извлекает tool calls
        
        Returns:
            Tuple(answer, tool_calls, sql_queries)
        """
        tool_calls = []
        sql_queries = []
        
        # Простой парсинг: ищем SQL запросы в ответе
        sql_pattern = r'execute_sql\("([^"]+)"\)'
        matches = re.findall(sql_pattern, ai_response)
        
        if matches:
            for sql in matches:
                # Валидируем и выполняем SQL
                if await self._validate_and_execute_sql(sql):
                    sql_queries.append(sql)
                    tool_calls.append("execute_sql")
        
        # Если есть tool calls, очищаем ответ от технических деталей
        answer = re.sub(sql_pattern, '', ai_response).strip()
        answer = re.sub(r'\(\)', '', answer).strip()
        
        # Если ответ пустой или только технические детали
        if not answer or len(answer) < 10:
            answer = "Данные получены. Что ещё вас интересует?"
        
        return answer, tool_calls, sql_queries
    
    async def _validate_and_execute_sql(self, sql: str) -> bool:
        """
        Валидирует и выполняет SQL запрос
        
        Returns:
            True если запрос выполнен успешно
        """
        sql_upper = sql.upper().strip()
        
        # 1. Проверяем на запрещённые ключевые слова
        for keyword in FORBIDDEN_KEYWORDS:
            if keyword in sql_upper:
                logger.warning(f"Forbidden keyword in SQL: {keyword}")
                return False
        
        # 2. Проверяем что это SELECT
        if not sql_upper.startswith("SELECT"):
            logger.warning(f"Not a SELECT query: {sql[:50]}...")
            return False
        
        # 3. Проверяем что таблица в разрешённом списке
        table_pattern = r'FROM\s+([a-zA-Z_][a-zA-Z0-9_.]*)'
        table_matches = re.findall(table_pattern, sql_upper)
        
        for table in table_matches:
            table_lower = table.lower()
            # Проверяем полное имя таблицы (с схемой)
            if '.' in table_lower:
                if table_lower not in ALLOWED_TABLES:
                    logger.warning(f"Table not in allowed list: {table_lower}")
                    return False
            else:
                # Если таблица без схемы, ищем по имени
                found = False
                for allowed in ALLOWED_TABLES:
                    if allowed.endswith(f".{table_lower}"):
                        found = True
                        break
                if not found:
                    logger.warning(f"Table not in allowed list: {table_lower}")
                    return False
        
        # 4. Добавляем LIMIT если нет
        if "LIMIT" not in sql_upper:
            sql = sql + " LIMIT 100"
        
        # 5. Выполняем запрос
        try:
            logger.info(f"Executing SQL: {sql[:200]}...")
            result = self.db.execute(text(sql))
            rows = result.fetchall()
            logger.info(f"SQL returned {len(rows)} rows")
            return True
        except Exception as e:
            logger.error(f"SQL execution failed: {e}")
            return False


class ChatToolService:
    """Сервис для выполнения инструментов чата"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def execute_sql(self, sql: str) -> Dict[str, Any]:
        """
        Выполняет SELECT запрос к БД
        
        Args:
            sql: SQL запрос
            
        Returns:
            Результат запроса
        """
        # Валидация
        if not ChatService._validate_sql(sql):
            return {
                "success": False,
                "error": "Invalid SQL query"
            }
        
        try:
            result = self.db.execute(text(sql))
            rows = result.fetchall()
            columns = result.keys()
            
            # Преобразуем в список словарей
            data = [dict(zip(columns, row)) for row in rows]
            
            return {
                "success": True,
                "data": data,
                "row_count": len(data)
            }
        except Exception as e:
            logger.error(f"SQL execution failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    def _validate_sql(sql: str) -> bool:
        """Валидирует SQL запрос"""
        sql_upper = sql.upper().strip()
        
        # Проверяем на запрещённые ключевые слова
        for keyword in FORBIDDEN_KEYWORDS:
            if keyword in sql_upper:
                return False
        
        # Проверяем что это SELECT
        if not sql_upper.startswith("SELECT"):
            return False
        
        return True
    
    def get_project_metrics(self, project_key: str) -> Dict[str, Any]:
        """
        Получает метрики проекта
        
        Args:
            project_key: Ключ проекта (например, "PROJ")
            
        Returns:
            Метрики проекта
        """
        from app.services.metrics.workload_index import calculate_workload_index
        from app.services.metrics.sla_score import calculate_sla_score
        from app.services.metrics.health_score import calculate_health_score
        from app.db.models import JiraIssue
        
        # Получаем данные
        assignees = self.db.query(JiraIssue.assignee_account_id).filter(
            JiraIssue.project_key == project_key,
            JiraIssue.assignee_account_id.isnot(None)
        ).distinct().all()
        
        workload_values = []
        for (assignee_id,) in assignees:
            wi = calculate_workload_index(self.db, assignee_id, project_key, weeks=2)
            if wi:
                workload_values.append(wi)
        
        avg_workload = sum(workload_values) / len(workload_values) if workload_values else 0
        
        sla = calculate_sla_score(self.db, project_key=project_key, period_days=30)
        health = calculate_health_score(self.db, project_key=project_key)
        
        return {
            "project_key": project_key,
            "workload_index": round(avg_workload, 2),
            "sla_score": round(sla['sla_score'], 1),
            "health_score": health['health_score'],
            "status": health['status']
        }
    
    def get_user_workload(self, user_id: str) -> Dict[str, Any]:
        """
        Получает загрузку пользователя
        
        Args:
            user_id: ID пользователя (account_id)
            
        Returns:
            Загрузка пользователя
        """
        from app.db.models import JiraIssue
        
        # Получаем задачи пользователя
        issues = self.db.query(JiraIssue).filter(
            JiraIssue.assignee_account_id == user_id,
            JiraIssue.status.notin_(['Done', 'Closed', 'Готово'])
        ).all()
        
        # Группируем по проектам
        projects = {}
        for issue in issues:
            if issue.project_key not in projects:
                projects[issue.project_key] = {"count": 0, "sp": 0}
            projects[issue.project_key]["count"] += 1
            projects[issue.project_key]["sp"] += issue.story_points or 0
        
        return {
            "user_id": user_id,
            "total_tasks": len(issues),
            "total_story_points": sum(p["sp"] for p in projects.values()),
            "projects": projects
        }
