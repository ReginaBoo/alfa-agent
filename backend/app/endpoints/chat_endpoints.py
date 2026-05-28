"""
Эндпоинты для умного чата с AI
"""
import uuid
import logging
import json
import re
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.db.models import User
from app.services.ai.chat_service import ChatService, ChatToolService, ALLOWED_TABLES, FORBIDDEN_KEYWORDS
from app.services.ai.providers.openrouter_provider import OpenRouterProvider
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================
# Pydantic модели
# ============================================================

class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None
    history: List[ChatMessage] = []


class ChatResponse(BaseModel):
    answer: str
    session_id: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SqlExecuteRequest(BaseModel):
    sql: str = Field(..., min_length=10, max_length=2000)
    session_id: Optional[str] = None


class SqlExecuteResponse(BaseModel):
    success: bool
    data: Optional[List[Dict[str, Any]]] = None
    row_count: int = 0
    error: Optional[str] = None


class ToolCallRequest(BaseModel):
    tool_name: str = Field(..., pattern="^(execute_sql|get_project_metrics|get_user_workload)$")
    params: Dict[str, Any]
    session_id: Optional[str] = None


class ToolCallResponse(BaseModel):
    success: bool
    tool_name: str
    data: Any
    error: Optional[str] = None


class ChatSessionResponse(BaseModel):
    session_id: str
    messages_count: int
    created_at: str


# ============================================================
# Хелперы
# ============================================================

def _get_ai_provider() -> OpenRouterProvider:
    """Создаёт экземпляр AI провайдера"""
    return OpenRouterProvider(
        api_key=settings.OPENROUTER_API_KEY,
        model=settings.OPENROUTER_MODEL
    )


def _validate_sql_query(sql: str) -> tuple[bool, str]:
    """
    Валидирует SQL запрос на безопасность
    
    Returns:
        (is_valid, error_message)
    """
    sql_upper = sql.upper().strip()
    
    # 1. Проверяем на запрещённые ключевые слова
    for keyword in FORBIDDEN_KEYWORDS:
        if keyword in sql_upper:
            return False, f"Forbidden keyword: {keyword}"
    
    # 2. Проверяем что это SELECT
    if not sql_upper.startswith("SELECT"):
        return False, "Only SELECT queries are allowed"
    
    # 3. Проверяем что таблицы в разрешённом списке
    table_pattern = r'FROM\s+([a-zA-Z_][a-zA-Z0-9_.]*)'
    table_matches = re.findall(table_pattern, sql_upper)
    
    for table in table_matches:
        table_lower = table.lower()
        if '.' in table_lower:
            if table_lower not in ALLOWED_TABLES:
                return False, f"Table not allowed: {table_lower}"
        else:
            found = False
            for allowed in ALLOWED_TABLES:
                if allowed.endswith(f".{table_lower}"):
                    found = True
                    break
            if not found:
                return False, f"Table not allowed: {table_lower}"
    
    return True, ""


def _execute_safe_sql(db: Session, sql: str, max_rows: int = 100) -> SqlExecuteResponse:
    """
    Безопасно выполняет SQL запрос
    
    Args:
        db: Сессия БД
        sql: SQL запрос
        max_rows: Максимальное количество строк
        
    Returns:
        Результат выполнения
    """
    # Валидация
    is_valid, error_msg = _validate_sql_query(sql)
    if not is_valid:
        logger.warning(f"SQL validation failed: {error_msg}")
        return SqlExecuteResponse(success=False, error=error_msg, row_count=0)
    
    # Добавляем LIMIT если нет
    sql_upper = sql.upper()
    if "LIMIT" not in sql_upper:
        sql = sql + f" LIMIT {max_rows}"
    else:
        # Проверяем что LIMIT не больше max_rows
        limit_match = re.search(r'LIMIT\s+(\d+)', sql_upper)
        if limit_match:
            limit_value = int(limit_match.group(1))
            if limit_value > max_rows:
                sql = re.sub(r'LIMIT\s+\d+', f'LIMIT {max_rows}', sql, flags=re.IGNORECASE)
    
    # Логируем запрос
    logger.info(f"Executing SQL: {sql[:200]}...")
    
    try:
        result = db.execute(text(sql))
        rows = result.fetchall()
        columns = list(result.keys())
        
        # Преобразуем в список словарей
        data = []
        for row in rows:
            row_dict = {}
            for i, col in enumerate(columns):
                value = row[i]
                # Преобразуем datetime в строку для JSON сериализации
                if hasattr(value, 'isoformat'):
                    value = value.isoformat()
                row_dict[col] = value
            data.append(row_dict)
        
        logger.info(f"SQL returned {len(data)} rows")
        
        return SqlExecuteResponse(
            success=True,
            data=data,
            row_count=len(data)
        )
        
    except Exception as e:
        logger.error(f"SQL execution failed: {e}")
        return SqlExecuteResponse(success=False, error=str(e), row_count=0)


# ============================================================
# Эндпоинты
# ============================================================

@router.post("/chat/completion")
@router.post("/api/chat/completion")
async def chat_completion(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Базовый чат с AI.
    
    Принимает сообщение пользователя и возвращает ответ AI.
    Поддерживает историю сообщений (до 10 последних).
    
    Пример запроса:
    {
        "message": "Сколько задач у Ивана?",
        "session_id": "uuid",
        "history": [
            {"role": "user", "content": "..."},
            {"role": "assistant", "content": "..."}
        ]
    }
    """
    # Генерируем session_id если не передан
    session_id = request.session_id or str(uuid.uuid4())
    
    # Создаём AI провайдер
    ai_provider = _get_ai_provider()
    
    # Создаём сервис чата
    chat_service = ChatService(db, ai_provider)
    
    # Преобразуем историю
    history = [{"role": msg.role, "content": msg.content} for msg in request.history]
    
    # Устанавливаем сессию
    chat_service.set_session(session_id, history)
    
    # Обрабатываем сообщение
    try:
        result = await chat_service.process_message(request.message)
        return ChatResponse(**result)
    except Exception as e:
        logger.error(f"Chat completion error: {e}")
        return ChatResponse(
            answer="Извините, произошла ошибка при обработке запроса. Попробуйте позже.",
            session_id=session_id,
            metadata={"error": str(e), "sql_queries": [], "tool_calls": []}
        )


@router.post("/chat/tools/execute-sql")
@router.post("/api/chat/tools/execute-sql")
def execute_sql_tool(
    request: SqlExecuteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Выполняет безопасный SQL запрос.
    
    Только SELECT запросы!
    Максимум 100 строк.
    Только разрешённые таблицы.
    
    Пример запроса:
    {
        "sql": "SELECT project_key, COUNT(*) FROM normalized.jira_issues GROUP BY project_key LIMIT 10"
    }
    """
    result = _execute_safe_sql(db, request.sql)
    return result


@router.post("/chat/tools/call")
@router.post("/api/chat/tools/call")
def call_tool(
    request: ToolCallRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Выполняет инструмент чата.
    
    Доступные инструменты:
    - execute_sql — выполнить SQL запрос
    - get_project_metrics — получить метрики проекта
    - get_user_workload — получить загрузку пользователя
    """
    tool_service = ChatToolService(db)
    
    try:
        if request.tool_name == "execute_sql":
            sql = request.params.get("sql", "")
            result = _execute_safe_sql(db, sql)
            return ToolCallResponse(
                success=result.success,
                tool_name=request.tool_name,
                data=result.model_dump(),
                error=result.error
            )
            
        elif request.tool_name == "get_project_metrics":
            project_key = request.params.get("project_key", "")
            if not project_key:
                return ToolCallResponse(
                    success=False,
                    tool_name=request.tool_name,
                    data=None,
                    error="project_key is required"
                )
            result = tool_service.get_project_metrics(project_key)
            return ToolCallResponse(
                success=True,
                tool_name=request.tool_name,
                data=result
            )
            
        elif request.tool_name == "get_user_workload":
            user_id = request.params.get("user_id", "")
            if not user_id:
                return ToolCallResponse(
                    success=False,
                    tool_name=request.tool_name,
                    data=None,
                    error="user_id is required"
                )
            result = tool_service.get_user_workload(user_id)
            return ToolCallResponse(
                success=True,
                tool_name=request.tool_name,
                data=result
            )
            
        else:
            return ToolCallResponse(
                success=False,
                tool_name=request.tool_name,
                data=None,
                error=f"Unknown tool: {request.tool_name}"
            )
            
    except Exception as e:
        logger.error(f"Tool call error: {e}")
        return ToolCallResponse(
            success=False,
            tool_name=request.tool_name,
            data=None,
            error=str(e)
        )


@router.get("/chat/history/{session_id}")
@router.get("/api/chat/history/{session_id}")
def get_chat_history(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Возвращает историю чата по session_id.
    
    Примечание: хранение истории на бэкенде не реализовано.
    Используйте localStorage на фронте для хранения истории.
    """
    return {
        "session_id": session_id,
        "message": "History storage is not implemented on backend. Use localStorage on frontend.",
        "messages": []
    }


@router.get("/chat/allowed-tables")
@router.get("/api/chat/allowed-tables")
def get_allowed_tables(
    current_user: User = Depends(get_current_user)
):
    """
    Возвращает список разрешённых таблиц для SQL запросов.
    """
    return {
        "tables": sorted(list(ALLOWED_TABLES)),
        "description": "Only SELECT queries allowed. Max 100 rows."
    }


@router.post("/chat/ai-completion")
@router.post("/api/chat/ai-completion")
async def ai_chat_completion(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Улучшенный чат с AI.
    AI анализирует вопрос и возвращает SQL, который мы выполняем.
    """
    session_id = request.session_id or str(uuid.uuid4())
    
    try:
        ai_provider = _get_ai_provider()
        
        # ШАГ 1: AI генерирует SQL запрос
        system_prompt = _build_system_prompt_with_schema()
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": request.message}
        ]
        
        ai_response = await ai_provider.chat_completions(messages)
        print(f"AI Response: {ai_response[:500]}")
        
        # ШАГ 2: Извлекаем SQL из ответа
        sql_queries = _extract_sql_queries(ai_response)
        print(f"Extracted SQL queries: {sql_queries}")
        
        # ШАГ 3: Выполняем SQL запросы
        all_results = []
        executed_sqls = []
        
        for sql in sql_queries[:3]:
            result = _execute_safe_sql(db, sql)
            print(f"SQL result: success={result.success}, rows={result.row_count}")
            if result.success and result.data:
                all_results.extend(result.data[:10])
                executed_sqls.append(sql)
        
        # ШАГ 4: Формируем ответ
        if all_results:
            # У нас есть реальные данные из БД
            answer = _format_results_as_answer(all_results, request.message)
        else:
            # Если SQL не найден или не выполнился
            answer = "Не удалось получить данные. Попробуйте переформулировать вопрос."
        
        return ChatResponse(
            answer=answer,
            session_id=session_id,
            metadata={
                "sql_queries": executed_sqls,
                "rows_count": len(all_results)
            }
        )
        
    except Exception as e:
        logger.error(f"AI chat error: {e}")
        return ChatResponse(
            answer="Извините, произошла ошибка.",
            session_id=session_id,
            metadata={"error": str(e)}
        )


def _format_results_as_answer(results: List[Dict], question: str) -> str:
    """Форматирует результаты SQL в читаемый ответ"""
    if not results:
        return "Данные не найдены."
    
    question_lower = question.lower()
    
    # Определяем тип вопроса
    if 'проблемн' in question_lower or 'хуже' in question_lower:
        # Ищем самый проблемный проект
        if 'project_key' in results[0]:
            # Сортируем если есть показатели
            if 'overdue_count' in results[0]:
                sorted_results = sorted(results, key=lambda x: x.get('overdue_count', 0), reverse=True)
            elif 'bug_count' in results[0]:
                sorted_results = sorted(results, key=lambda x: x.get('bug_count', 0), reverse=True)
            else:
                sorted_results = results
            
            worst = sorted_results[0]
            project = worst.get('project_key', 'Неизвестно')
            return f"Самый проблемный проект — {project}. Подробнее: {json.dumps(worst, ensure_ascii=False, default=str)}"
    
    # Универсальный ответ для списков
    if len(results) == 1:
        # Одна запись
        parts = []
        for key, value in results[0].items():
            if value is not None and key not in ['id', 'issue_id']:
                parts.append(f"{key}: {value}")
        return f"Найдено: {', '.join(parts)}"
    else:
        # Много записей
        first = results[0]
        keys = list(first.keys())[:3]
        summary = []
        for key in keys:
            if key in first:
                summary.append(f"{key}: {first[key]}")
        
        return f"Найдено {len(results)} записей. Например: {', '.join(summary)}"


def _extract_sql_queries(text: str) -> List[str]:
    """Извлекает SQL запросы из текста"""
    sql_queries = []
    
    # Ищем SQL в markdown блоках
    pattern = r'```sql\s*\n(.*?)\n```'
    matches = re.findall(pattern, text, re.DOTALL)
    
    for match in matches:
        sql = match.strip()
        if sql and sql.upper().startswith('SELECT'):
            sql_queries.append(sql)
    
    # Ищем SQL в кавычках после execute_sql
    if not sql_queries:
        pattern = r'execute_sql\([\'"]([^\'"]+)[\'"]\)'
        matches = re.findall(pattern, text)
        for match in matches:
            if match and match.upper().startswith('SELECT'):
                sql_queries.append(match)
    
    # Ищем просто SELECT ... (без блоков)
    if not sql_queries:
        pattern = r'(SELECT\s+.*?)(?=\n\n|\Z)'
        matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
        for match in matches:
            sql = match.strip()
            if sql and len(sql) > 10:
                sql_queries.append(sql)
    
    return sql_queries


# ============================================================
# Вспомогательные функции
# ============================================================

def _build_system_prompt_with_schema() -> str:
    """Формирует системный промпт с описанием схемы БД"""
    return """Ты — умный аналитический ассистент для платформы Alpha Agent.
Ты имеешь доступ к базе данных проектов Jira и GitHub.

СХЕМА БАЗЫ ДАННЫХ:

1. normalized.jira_issues — задачи Jira
   - id (integer)
   - issue_key (string) — ключ задачи, например "PROJ-123"
   - project_key (string) — ключ проекта
   - summary (text) — название задачи
   - status (string) — статус: "To Do", "In Progress", "Done", "Closed"
   - status_category (string) — "To Do", "In Progress", "Done"
   - assignee_account_id (string) — ID исполнителя
   - assignee_name (string) — имя исполнителя
   - reporter_account_id (string) — ID создателя
   - priority (string) — приоритет: "Highest", "High", "Medium", "Low"
   - issue_type (string) — тип: "Story", "Task", "Bug", "Epic"
   - story_points (float) — story points
   - original_estimate (float) — оценка в часах
   - time_spent (float) — затраченное время
   - remaining_estimate (float) — оставшееся время
   - due_date (datetime) — дедлайн
   - closed_at (datetime) — дата закрытия
   - created_at (datetime) — дата создания
   - updated_at (datetime) — дата обновления
   - parent_issue_id (integer) — ID родительской задачи
   - is_deleted (boolean)

2. normalized.issue_changelog — история изменений
   - issue_key (string)
   - field_name (string) — изменённое поле
   - from_value (text) — старое значение
   - to_value (text) — новое значение
   - changed_at (datetime)
   - author_account_id (string)

3. core.projects — проекты
   - id (integer)
   - key (string)
   - name (string)
   - jira_project_key (string)
   - is_active (boolean)

4. normalized.github_pull_requests — Pull Requests GitHub
   - pr_id (integer)
   - title (text)
   - state (string) — "open", "closed"
   - author_login (string)
   - created_at (datetime)
   - merged (boolean)
   - additions (integer)
   - deletions (integer)

5. normalized.github_commits — коммиты GitHub
   - commit_sha (string)
   - author_login (string)
   - message (text)
   - additions (integer)
   - deletions (integer)
   - committed_at (datetime)

============================================================
ИНТЕРПРЕТАЦИЯ ВОПРОСОВ ПОЛЬЗОВАТЕЛЯ
============================================================

Когда пользователь спрашивает о «проблемах» или «проблемных проектах», 
используй ЭТИ критерии (не приоритет!):

1. Просроченные задачи (due_date < NOW() И статус не Done/Closed)
2. Баги (issue_type = 'Bug' И статус не Done/Closed)
3. Задачи в статусе слишком долго (старые created_at)

«Проблемный проект» = проект с БОЛЬШИМ количеством:
- Просроченных задач
- Багов
- Старых незакрытых задач

============================================================
ПРАВИЛА ДЛЯ AI:
============================================================

1. Для получения данных используй SQL запросы
2. ТОЛЬКО SELECT запросы
3. ВСЕГДА добавляй LIMIT 100
4. Используй схему: normalized.jira_issues, core.projects и т.д.

ВАЖНО: SQL запросы пиши ТОЛЬКО внутри блоков ```sql ... ```. 
Эти блоки будут извлечены бэкендом и выполнены автоматически.
Пользователь НЕ ДОЛЖЕН видеть SQL запросы в ответе.

ПОСЛЕ SQL блока напиши краткий текстовый ответ (2-3 предложения).
Текстовый ответ будет показан пользователю.

Пример правильного ответа AI:
```sql
SELECT project_key, COUNT(*) FROM normalized.jira_issues WHERE status NOT IN ('Done', 'Closed') GROUP BY project_key LIMIT 100
```
Анализирую данные по проектам...

В этом примере:
- SQL будет извлечён и выполнен бэкендом
- Текст "Анализирую данные по проектам..." будет показан пользователю
- Бэкенд заменит текст на конкретный ответ с цифрами

============================================================
ПРИМЕРЫ SQL ЗАПРОСОВ:

Вопрос: «Какой проект самый проблемный?»
```sql
SELECT project_key, 
       COUNT(CASE WHEN due_date < NOW() AND status NOT IN ('Done', 'Closed') THEN 1 END) as overdue_count,
       COUNT(CASE WHEN issue_type = 'Bug' AND status NOT IN ('Done', 'Closed') THEN 1 END) as bugs_count
FROM normalized.jira_issues 
WHERE status NOT IN ('Done', 'Closed')
GROUP BY project_key 
ORDER BY overdue_count + bugs_count DESC 
LIMIT 10
```

Вопрос: «Сколько просроченных задач?»
```sql
SELECT COUNT(*) FROM normalized.jira_issues 
WHERE due_date < NOW() AND status NOT IN ('Done', 'Closed') 
LIMIT 100
```

Вопрос: «Где много багов?»
```sql
SELECT project_key, COUNT(*) as bug_count 
FROM normalized.jira_issues 
WHERE issue_type = 'Bug' AND status NOT IN ('Done', 'Closed') 
GROUP BY project_key 
ORDER BY bug_count DESC 
LIMIT 10
```"""



def _generate_answer_programmatically(tool_results: List, question: str) -> str:
    """
    Программно генерирует ответ на основе данных из БД.
    Это fallback если AI не может сформировать хороший ответ.
    """
    if not tool_results or not tool_results[0]:
        return "Данные не найдены."
    
    data = tool_results[0]
    question_lower = question.lower()
    
    # Определяем тип вопроса и формируем ответ
    if 'проблемн' in question_lower or 'неблагополучн' in question_lower:
        # Поиск проблемного проекта
        if isinstance(data, list) and len(data) > 0:
            # Сортируем по сумме проблем (если есть такие колонки)
            worst = data[0]
            project_key = worst.get('project_key', 'Неизвестно')
            overdue = worst.get('overdue_count', worst.get('overdue', 0))
            bugs = worst.get('bugs_count', worst.get('bugs', 0))
            old_issues = worst.get('old_issues_count', 0)
            
            parts = [f"Самый проблемный проект — {project_key}"]
            if overdue > 0:
                parts.append(f"{overdue} просроченных задач")
            if bugs > 0:
                parts.append(f"{bugs} бага")
            if old_issues > 0:
                parts.append(f"{old_issues} старых задач")
            
            return f"{', '.join(parts)}."
    
    elif 'просроченн' in question_lower:
        # Просроченные задачи
        if isinstance(data, list) and len(data) > 0:
            if 'count' in data[0]:
                count = data[0]['count']
                return f"Найдено {count} просроченных задач."
            elif 'overdue_count' in data[0]:
                count = data[0]['overdue_count']
                return f"Найдено {count} просроченных задач."
    
    elif 'баг' in question_lower:
        # Баги
        if isinstance(data, list) and len(data) > 0:
            if 'bug_count' in data[0] or 'bugs_count' in data[0]:
                count = data[0].get('bug_count', data[0].get('bugs_count', 0))
                project = data[0].get('project_key', 'Неизвестно')
                return f"В проекте {project} найдено {count} багов."
            elif 'count' in data[0]:
                count = data[0]['count']
                return f"Найдено {count} багов."
    
    elif 'задач' in question_lower and 'у' in question_lower:
        # Задачи у человека
        if isinstance(data, list) and len(data) > 0:
            name = data[0].get('assignee_name', data[0].get('name', 'Неизвестно'))
            count = data[0].get('count', data[0].get('task_count', 0))
            return f"У {name} {count} активных задач."
    
    # Универсальный ответ для списков
    if isinstance(data, list) and len(data) > 0:
        # Получаем первую запись
        first = data[0]
        keys = list(first.keys())
        
        # Формируем простой ответ
        summary = []
        for key in keys[:3]:  # Первые 3 колонки
            value = first.get(key, '')
            if value is not None and key != 'project_key':
                summary.append(f"{key}: {value}")
        
        if len(data) > 1:
            return f"Найдено {len(data)} записей. Первая: {', '.join(summary)}"
        else:
            return f"Найдено: {', '.join(summary)}"
    
    return "Анализ данных завершён."
