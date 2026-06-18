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
    Затем AI формирует ответ на основе полученных данных.
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
        logger.info(f"AI Response (SQL gen): {ai_response[:1000] if len(ai_response) > 1000 else ai_response}")
        
        # ШАГ 2: Извлекаем SQL из ответа
        sql_queries = _extract_sql_queries(ai_response)
        logger.info(f"Extracted SQL queries: {sql_queries}")
        
        # Если SQL не найден — это обычный разговорный ответ, возвращаем его
        if not sql_queries:
            logger.info("No SQL found, returning conversational AI response")
            # Очищаем ответ от markdown блоков если они есть
            clean_answer = re.sub(r'```sql\s*\n.*?\n```', '', ai_response, flags=re.DOTALL).strip()
            clean_answer = re.sub(r'```\s*\n.*?\n```', '', clean_answer, flags=re.DOTALL).strip()
            if clean_answer:
                return ChatResponse(
                    answer=clean_answer,
                    session_id=session_id,
                    metadata={
                        "sql_queries": [],
                        "rows_count": 0
                    }
                )
            
            # Fallback: пробуем программно сгенерировать SQL
            logger.info("Trying programmatic SQL generation...")
            sql_queries = _generate_sql_from_question(request.message)
            logger.info(f"Programmatic SQL queries: {sql_queries}")
        
        # ШАГ 3: Выполняем SQL запросы
        all_results = []
        executed_sqls = []
        
        for sql in sql_queries[:3]:
            logger.info(f"Attempting to execute SQL: {sql[:200]}...")
            result = _execute_safe_sql(db, sql)
            logger.info(f"SQL result: success={result.success}, rows={result.row_count}, error={result.error}")
            if result.success and result.data:
                all_results.extend(result.data[:10])
                executed_sqls.append(sql)
        
        # ШАГ 4: AI формирует ответ на основе данных
        if all_results:
            logger.info(f"Got {len(all_results)} results, generating answer...")
            # Отправляем данные AI для формирования ответа
            data_prompt = f"""Пользователь спросил: "{request.message}"

Данные из базы данных:
{json.dumps(all_results[:10], ensure_ascii=False, default=str)}

Сформулируй краткий ответ на русском языке (2-3 предложения).
Используй конкретные цифры и имена из данных.
Не упоминай SQL или технические детали.
Отвечай понятным языком, как аналитик."""

            answer_messages = [
                {"role": "system", "content": "Ты — аналитический ассистент Alpha Agent. Отвечай кратко и по существу. НИКОГДА не выдумывай информацию, которой нет в данных. Если данных недостаточно, так и скажи."},
                {"role": "user", "content": data_prompt}
            ]
            
            try:
                answer = await ai_provider.chat_completions(answer_messages)
                answer = answer.strip()
                logger.info(f"Final AI answer: {answer[:500]}")
            except Exception as e:
                logger.warning(f"AI answer generation failed: {e}")
                # Fallback: программный ответ
                answer = _format_results_as_answer(all_results, request.message)
                logger.info(f"Using fallback answer: {answer}")
        else:
            # Если SQL не найден или не выполнился
            logger.warning(f"No SQL queries extracted or executed. AI response: {ai_response[:500]}")
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
        logger.error(f"AI chat error: {e}", exc_info=True)
        return ChatResponse(
            answer="Извините, произошла ошибка.",
            session_id=session_id,
            metadata={"error": str(e)}
        )


def _format_results_as_answer(results: List[Dict], question: str) -> str:
    """Форматирует результаты SQL в читаемый ответ"""
    if not results:
        return "Данные не найдены. Попробуйте переформулировать вопрос или уточнить название проекта."
    
    question_lower = question.lower()
    
    # Если вопрос про задачи конкретного человека
    if ('работает' in question_lower or 'занят' in question_lower or 'задач' in question_lower) and 'assignee_name' in results[0]:
        name = results[0].get('assignee_name', 'Неизвестно')
        if len(results) == 1 and 'issue_key' not in results[0]:
            # Это может быть агрегированный ответ
            count = results[0].get('count', results[0].get('task_count', 0))
            return f"У {name} {count} активных задач."
        
        # Список задач
        task_parts = []
        for item in results[:5]:
            key = item.get('issue_key', '')
            summary = item.get('summary', '')
            status = item.get('status', '')
            if key and summary:
                task_parts.append(f"{key} — «{summary}» ({status})")
        
        if task_parts:
            return f"У {name} {len(results)} активных задач: {'; '.join(task_parts)}."
        else:
            return f"У {name} {len(results)} активных задач."

    # Если вопрос про баги
    if 'баг' in question_lower and 'bug_count' in results[0]:
        count = results[0]['bug_count']
        project = results[0].get('project_name', results[0].get('project_key', 'проекте'))
        if count == 0:
            return f"В проекте {project} нет открытых багов."
        return f"В проекте {project} найдено {count} багов."

    # Если вопрос про закрытые задачи
    if ('закрыт' in question_lower or 'done' in question_lower) and 'issue_key' in results[0]:
        task_parts = []
        for item in results[:10]:
            key = item.get('issue_key', '')
            summary = item.get('summary', '')
            closed_at = item.get('closed_at', '')
            if key and summary:
                if closed_at:
                    # Форматируем дату
                    if isinstance(closed_at, str):
                        date_str = closed_at[:10] if len(closed_at) >= 10 else closed_at
                    else:
                        date_str = str(closed_at)
                    task_parts.append(f"{key} «{summary}» (закрыта {date_str})")
                else:
                    task_parts.append(f"{key} «{summary}»")
        
        if task_parts:
            return f"Закрытые задачи: {'; '.join(task_parts)}."
        else:
            return f"Найдено {len(results)} закрытых задач."
    
    # Определяем тип вопроса
    if 'проблемн' in question_lower or 'хуже' in question_lower:
        # Ищем самый проблемный проект
        if 'project_name' in results[0] or 'project_key' in results[0]:
            # Сортируем по сумме проблем
            if 'total_problems' in results[0]:
                sorted_results = sorted(results, key=lambda x: x.get('total_problems', 0), reverse=True)
            elif 'overdue' in results[0] or 'overdue_count' in results[0]:
                sorted_results = sorted(results, key=lambda x: x.get('overdue', x.get('overdue_count', 0)) + x.get('bug_count', x.get('bugs', 0)), reverse=True)
            elif 'bug_count' in results[0] or 'bugs_count' in results[0]:
                sorted_results = sorted(results, key=lambda x: x.get('bug_count', x.get('bugs_count', 0)), reverse=True)
            else:
                sorted_results = results
            
            worst = sorted_results[0]
            project_name = worst.get('project_name') or worst.get('project_key', 'Неизвестно')
            
            # Формируем подробный ответ с конкретикой
            overdue = worst.get('overdue_count', worst.get('overdue', 0))
            bugs = worst.get('bug_count', worst.get('bugs', worst.get('bugs_count', 0)))
            old = worst.get('old_tasks', 0)
            total = worst.get('open_tasks', worst.get('count', 0))
            total_problems = worst.get('total_problems', overdue + bugs)
            
            details = []
            if total:
                details.append(f"{total} открытых задач")
            if overdue:
                details.append(f"{overdue} просроченных")
            if bugs:
                details.append(f"{bugs} багов")
            if old:
                details.append(f"{old} старых задач")
            
            if details:
                return f"Самый проблемный проект — {project_name} ({total_problems} проблем): {', '.join(details)}."
            else:
                return f"Самый проблемный проект — {project_name} ({total_problems} проблем)."
    
    # Закрытые задачи в проекте
    if ('закрыт' in question_lower or 'done' in question_lower or 'closed' in question_lower) and 'проект' in question_lower:
        if 'issue_key' in results[0] or 'issue_id' in results[0]:
            # Список задач
            parts = []
            for item in results[:5]:
                key = item.get('issue_key') or item.get('issue_id', '')
                summary = item.get('summary', '')
                closed_at = item.get('closed_at', '')
                if key and summary:
                    if closed_at:
                        parts.append(f"{key} — «{summary}» (закрыта {closed_at})")
                    else:
                        parts.append(f"{key} — «{summary}»")
            
            if len(results) == 1:
                return f"В проекте закрыта {len(results)} задача: {parts[0]}."
            else:
                return f"В проекте закрыто {len(results)} задач. Например: {'; '.join(parts)}."
        elif 'closed_count' in results[0] or 'count' in results[0]:
            count = results[0].get('closed_count', results[0].get('count', 0))
            return f"В проекте закрыто {count} задач."
    
    # Участники проекта / кто загружен
    if ('участник' in question_lower or 'загружен' in question_lower or 'команд' in question_lower) and 'проект' in question_lower:
        if 'assignee_name' in results[0]:
            parts = []
            for item in results:
                name = item.get('assignee_name', 'Не назначено')
                count = item.get('task_count', item.get('count', 0))
                if name:
                    parts.append(f"{name} — {count} задач")
            
            if parts:
                return f"Участники проекта: {'; '.join(parts)}."
            else:
                return "В проекте нет участников с активными задачами."
        elif 'total_members' in results[0]:
            return f"В проекте {results[0]['total_members']} участников."
    
    # Story points по исполнителям
    if 'story' in question_lower and 'point' in question_lower and ('исполнител' in question_lower or 'команд' in question_lower):
        if 'assignee_name' in results[0] and ('total_story_points' in results[0] or 'story_points' in results[0]):
            parts = []
            for item in results:
                name = item.get('assignee_name', 'Не назначено')
                sp = item.get('total_story_points', item.get('story_points', 0))
                if name:
                    parts.append(f"{name} — {sp} SP")
            
            if parts:
                return f"Story points по исполнителям: {'; '.join(parts)}."
    
    # Story points одной задачи
    if 'story' in question_lower and 'point' in question_lower:
        if 'story_points' in results[0]:
            sp = results[0]['story_points']
            summary = results[0].get('summary', '')
            issue_key = results[0].get('issue_key', '')
            if sp is not None and sp != 0:
                return f"У задачи {issue_key} «{summary}» story points = {sp}."
            else:
                return f"У задачи {issue_key} «{summary}» story points не указаны."
    
    # Просроченные задачи — показываем топ проектов
    if 'просроченн' in question_lower:
        if 'overdue_count' in results[0] and 'project_name' in results[0]:
            # Есть данные по проектам — показываем топ 3
            top_results = sorted(results, key=lambda x: x.get('overdue_count', 0), reverse=True)[:3]
            parts = []
            for i, item in enumerate(top_results, 1):
                project = item.get('project_name') or item.get('project_key', 'проект')
                count = item.get('overdue_count', 0)
                parts.append(f"{i}. {project} — {count}")
            
            if len(parts) == 1:
                return f"Проект {top_results[0].get('project_name', 'Неизвестно')} — {top_results[0].get('overdue_count', 0)} просроченных задач."
            else:
                return f"Топ проектов по просроченным задачам:\n" + "\n".join(parts)
        elif 'count' in results[0]:
            count = results[0]['count']
            return f"Найдено {count} просроченных задач."
        elif 'total' in results[0]:
            count = results[0]['total']
            return f"Найдено {count} просроченных задач."
    
    # Баги в проекте
    if 'баг' in question_lower and 'проект' in question_lower:
        if 'bug_count' in results[0]:
            count = results[0]['bug_count']
            project = results[0].get('project_name') or results[0].get('project_key', 'Неизвестно')
            return f"В проекте {project} найдено {count} багов."
        elif 'bugs_count' in results[0]:
            count = results[0]['bugs_count']
            project = results[0].get('project_name') or results[0].get('project_key', 'Неизвестно')
            return f"В проекте {project} найдено {count} багов."
        elif 'count' in results[0]:
            count = results[0]['count']
            project = results[0].get('project_name') or results[0].get('project_key', 'Неизвестно')
            return f"В проекте {project} найдено {count} багов."
    
    # Баги (без указания проекта)
    if 'баг' in question_lower:
        if 'bug_count' in results[0]:
            count = results[0]['bug_count']
            project = results[0].get('project_name') or results[0].get('project_key', 'Неизвестно')
            if len(results) == 1:
                return f"В проекте {project} найдено {count} багов."
            else:
                return f"Найдено {count} багов в проекте {project}."
        elif 'bugs_count' in results[0]:
            count = results[0]['bugs_count']
            project = results[0].get('project_name') or results[0].get('project_key', 'Неизвестно')
            return f"В проекте {project} найдено {count} багов."
        elif 'count' in results[0]:
            count = results[0]['count']
            return f"Найдено {count} багов."
    
    # Задачи конкретного человека (разные формулировки)
    if any(word in question_lower for word in ['работает', 'занят', 'занята', 'задач', 'активн']):
        # Проверяем, есть ли имя в вопросе
        name_in_question = _extract_name_from_question(question)
        if name_in_question:
            if 'assignee_name' in results[0] or 'name' in results[0]:
                name = results[0].get('assignee_name') or results[0].get('name', 'Неизвестно')
                count = results[0].get('count', results[0].get('task_count', 0))
                bugs = results[0].get('bug_count', 0)
                overdue = results[0].get('overdue_count', 0)
                
                # Если есть список задач
                if 'issue_key' in results[0] or 'summary' in results[0]:
                    task_parts = []
                    for item in results[:5]:
                        key = item.get('issue_key', '')
                        summary = item.get('summary', '')
                        status = item.get('status', '')
                        if key and summary:
                            task_parts.append(f"{key} — «{summary}»")
                    
                    if task_parts:
                        return f"У {name} {len(results)} активных задач: {'; '.join(task_parts)}."
                
                details = [f"{count} активных задач"]
                if bugs:
                    details.append(f"{bugs} багов")
                if overdue:
                    details.append(f"{overdue} просроченных")
                
                return f"У {name}: {', '.join(details)}."
            elif 'count' in results[0]:
                count = results[0]['count']
                return f"У {name_in_question} найдено {count} задач."
    
    # Задачи у человека (старый формат)
    if 'у' in question_lower and ('задач' in question_lower or 'task' in question_lower):
        if 'assignee_name' in results[0] or 'name' in results[0]:
            name = results[0].get('assignee_name') or results[0].get('name', 'Неизвестно')
            count = results[0].get('count', results[0].get('task_count', 0))
            bugs = results[0].get('bug_count', 0)
            overdue = results[0].get('overdue_count', 0)
            
            # Если есть список задач
            if 'issue_key' in results[0] or 'summary' in results[0]:
                task_parts = []
                for item in results[:5]:
                    key = item.get('issue_key', '')
                    summary = item.get('summary', '')
                    status = item.get('status', '')
                    if key and summary:
                        task_parts.append(f"{key} — «{summary}»")
                
                if task_parts:
                    return f"У {name} {len(results)} активных задач: {'; '.join(task_parts)}."
            
            details = [f"{count} активных задач"]
            if bugs:
                details.append(f"{bugs} багов")
            if overdue:
                details.append(f"{overdue} просроченных")
            
            return f"У {name}: {', '.join(details)}."
        elif 'count' in results[0]:
            count = results[0]['count']
            return f"Найдено {count} задач."
    
    # Подсчёт по проектам
    if 'проект' in question_lower and ('сколько' in question_lower or 'много' in question_lower):
        if 'project_name' in results[0] and 'count' in results[0]:
            project = results[0]['project_name']
            count = results[0]['count']
            return f"В проекте {project} найдено {count} записей."
    
    # Сколько задач (без указания человека) — показываем топ проектов
    if 'сколько' in question_lower and 'задач' in question_lower:
        if 'project_name' in results[0] and 'total_open' in results[0]:
            top_results = sorted(results, key=lambda x: x.get('total_open', 0), reverse=True)[:3]
            parts = []
            for i, item in enumerate(top_results, 1):
                project = item.get('project_name') or item.get('project_key', 'проект')
                total = item.get('total_open', 0)
                overdue = item.get('overdue', 0)
                bugs = item.get('bugs', 0)
                parts.append(f"{i}. {project} — {total} задач{('' if total == 1 else 'и' if total % 10 > 1 and total % 10 < 5 else '')}")
                if overdue or bugs:
                    extra = []
                    if overdue:
                        extra.append(f"{overdue} просроченных")
                    if bugs:
                        extra.append(f"{bugs} багов")
                    parts[-1] += f" ({', '.join(extra)})"
            
            return "Топ проектов по количеству задач:\n" + "\n".join(parts)
    
    # Открытые задачи в проекте
    if ('открыт' in question_lower or 'активн' in question_lower) and 'проект' in question_lower:
        if 'issue_key' in results[0] or 'summary' in results[0]:
            task_parts = []
            for item in results[:5]:
                key = item.get('issue_key', '')
                summary = item.get('summary', '')
                assignee = item.get('assignee_name', 'без исполнителя')
                status = item.get('status', '')
                if key and summary:
                    task_parts.append(f"{key} — «{summary}» ({assignee})")
            
            if task_parts:
                return f"В проекте открыто {len(results)} задач: {'; '.join(task_parts)}."
        elif 'open_count' in results[0] or 'count' in results[0]:
            count = results[0].get('open_count', results[0].get('count', 0))
            return f"В проекте открыто {count} задач."
    
    # Универсальный ответ для списков
    if len(results) == 1:
        # Одна запись
        parts = []
        for key, value in results[0].items():
            if value is not None and key not in ['id', 'issue_id', 'project_key']:
                parts.append(f"{key}: {value}")
        if parts:
            return f"Найдено: {', '.join(parts)}"
        else:
            return f"Найдено: {json.dumps(results[0], ensure_ascii=False, default=str)}"
    else:
        # Много записей
        first = results[0]
        keys = [k for k in list(first.keys())[:3] if k not in ['id', 'issue_id']]
        summary = []
        for key in keys:
            if key in first:
                summary.append(f"{key}: {first[key]}")
        
        if summary:
            return f"Найдено {len(results)} записей. Например: {', '.join(summary)}"
        else:
            return f"Найдено {len(results)} записей."


def _extract_name_from_question(question: str) -> Optional[str]:
    """Извлекает имя из вопроса с поддержкой разных вариантов"""
    question_lower = question.lower()
    
    # Расширенные паттерны для извлечения имени
    patterns = [
        r'у\s+([а-яёa-z0-9_.-]+)',  # у Ивана, у Alenakrash95
        r'([а-яёa-z0-9_.-]+)\s+работает',  # Иван работает
        r'([а-яёa-z0-9_.-]+)\s+занят',  # Иван занят
        r'([а-яёa-z0-9_.-]+)\s+задач',  # Иван задач
        r'задач\s+у\s+([а-яёa-z0-9_.-]+)',  # задач у Ивана
        r'([а-яёa-z0-9_.-]+)\s+в\s+проект',  # Алёна в проект
        r'над\s+чем\s+работает\s+([а-яёa-z0-9_.-]+)',  # над чем работает Алёна
        r'чем\s+занят(?:а)?\s+([а-яёa-z0-9_.-]+)',  # чем занята Алёна
    ]
    
    for pattern in patterns:
        match = re.search(pattern, question_lower)
        if match:
            raw_name = match.group(1)
            # Проверяем, что это не служебное слово
            if raw_name not in ['проект', 'команда', 'задача', 'баг']:
                return _normalize_name(raw_name)
    
    return None


def _extract_sql_queries(text: str) -> List[str]:
    """Извлекает SQL запросы из текста"""
    sql_queries = []
    
    # Ищем SQL в markdown блоках
    pattern = r'```sql\s*\n(.*?)\n```'
    matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
    
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
    
    # Ищем SQL в markdown блоках без указания языка
    if not sql_queries:
        pattern = r'```\s*\n(SELECT\s+.*?)\n```'
        matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
        for match in matches:
            sql = match.strip()
            if sql and sql.upper().startswith('SELECT'):
                sql_queries.append(sql)
    
    # Ищем просто SELECT ... (без блоков) — более агрессивный поиск
    if not sql_queries:
        # Ищем SELECT до LIMIT или GROUP BY или ORDER BY
        pattern = r'(SELECT\s+[^(]*?(?:FROM\s+[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?\s+)?(?:WHERE\s+[^LIMIT]*?\s+)?(?:LIMIT\s+\d+)?(?:GROUP\s+BY\s+[^L]*?)?(?:ORDER\s+BY\s+[^L]*?)?)'
        matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
        for match in matches:
            sql = match.strip()
            if sql and len(sql) > 20 and 'SELECT' in sql.upper():
                sql_queries.append(sql)
    
    # Если ничего не нашли, пробуем найти любой SELECT запрос
    if not sql_queries:
        # Ищем SELECT ... FROM ... где есть таблица
        pattern = r'(SELECT\s+.*?\s+FROM\s+[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?.*?)(?:\n\n|\Z|```)'
        matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
        for match in matches:
            sql = match.strip()
            # Убираем лишнее
            sql = re.sub(r'\s+', ' ', sql).strip()
            if sql and len(sql) > 20 and 'SELECT' in sql.upper() and 'FROM' in sql.upper():
                # Убираем LIMIT если он больше 100
                if 'LIMIT' in sql.upper():
                    limit_match = re.search(r'LIMIT\s+(\d+)', sql, re.IGNORECASE)
                    if limit_match and int(limit_match.group(1)) > 100:
                        sql = re.sub(r'LIMIT\s+\d+', 'LIMIT 100', sql, flags=re.IGNORECASE)
                sql_queries.append(sql)
    
    return sql_queries


# ============================================================
# Вспомогательные функции
# ============================================================

def _build_system_prompt_with_schema() -> str:
    """Формирует системный промпт с описанием схемы БД"""
    return """Ты — умный аналитический ассистент для платформы Alpha Agent.
Ты имеешь доступ к данным проектов Jira и GitHub.

СХЕМА ДАННЫХ:

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
   - key (string) — ключ проекта (например "KANBAN")
   - name (string) — название проекта (например "CRM Система")
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
ПРАВИЛА ДЛЯ AI:
============================================================

1. ВСЕГДА пиши SQL запрос в markdown блоке с языком sql: ```sql ... ```
2. ТОЛЬКО SELECT запросы
3. ВСЕГДА добавляй LIMIT 100
4. Используй схему: normalized.jira_issues, core.projects и т.д.
5. После SQL блока напиши краткий ответ (2-3 предложения)
6. В ответах НЕ упоминай "база данных", "БД", "таблица" — отвечай как аналитик
7. Для получения названий проектов используй JOIN:
   ```sql
   SELECT ji.project_key, p.name as project_name
   FROM normalized.jira_issues ji
   LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key
   ```
8. НИКОГДА не выдумывай информацию, которой нет в данных! Если данных недостаточно — так и скажи.
9. НЕ отвечай на вопросы о "фокусе команды", "целях проекта", "стратегии" — эти данные недоступны.
ПРИМЕР ПРАВИЛЬНОГО ОТВЕТА:
```SELECT p.name as project_name, ji.project_key, COUNT(*) as open_tasks FROM normalized.jira_issues ji LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key WHERE ji.status NOT IN ('Done', 'Closed', 'Готово') GROUP BY p.name, ji.project_key LIMIT 10```
Анализирую данные по проектам...
============================================================
ПРИМЕРЫ ВОПРОСОВ И ОТВЕТОВ:
Вопрос: «Привет»
Ответ: Здравствуйте! Чем я могу вам помочь сегодня?
Вопрос: «Какой проект самый проблемный?»
```SELECT project_name, project_key, overdue, bugs, (overdue + bugs) as total_problems FROM (SELECT p.name as project_name, ji.project_key, COUNT(*) FILTER (WHERE ji.due_date < NOW()) as overdue, COUNT(*) FILTER (WHERE ji.issue_type = 'Bug') as bugs FROM normalized.jira_issues ji LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key WHERE ji.status NOT IN ('Done', 'Closed', 'Готово') GROUP BY p.name, ji.project_key) AS subq ORDER BY total_problems DESC LIMIT 10```
Ответ: Топ проектов с наибольшим количеством проблем...
Вопрос: «Сколько просроченных задач?»
```SELECT p.name as project_name, ji.project_key, COUNT(*) as overdue_count FROM normalized.jira_issues ji LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key WHERE ji.due_date < NOW() AND ji.status NOT IN ('Done', 'Closed', 'Готово') GROUP BY p.name, ji.project_key ORDER BY overdue_count DESC LIMIT 10```
Ответ: Топ проектов по просроченным задачам...
Вопрос: «Где много багов?»
```SELECT p.name as project_name, ji.project_key, COUNT(*) as bug_count FROM normalized.jira_issues ji LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key WHERE ji.issue_type = 'Bug' AND ji.status NOT IN ('Done', 'Closed', 'Готово') GROUP BY p.name, ji.project_key ORDER BY bug_count DESC LIMIT 10```
Ответ: Проекты с наибольшим количеством багов...
Вопрос: «Сколько задач у Ивана?»
```SELECT ji.assignee_name, COUNT(*) as task_count FROM normalized.jira_issues ji WHERE ji.assignee_name LIKE '%Иван%' AND ji.status NOT IN ('Done', 'Closed', 'Готово') GROUP BY ji.assignee_name LIMIT 10```
Ответ: У Ивана X активных задач...
Вопрос: «Покажи все проекты?»
```SELECT key, name, is_active FROM core.projects WHERE is_active = true LIMIT 100```
Ответ: Вот список проектов...
Вопрос: «Какие задачи в проекте Araka закрыты?»
```SELECT ji.issue_key, ji.summary, ji.closed_at FROM normalized.jira_issues ji LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key WHERE p.name ILIKE '%Araka%' AND ji.status IN ('Done', 'Closed', 'Готово') ORDER BY ji.closed_at DESC LIMIT 20```
Ответ: В проекте закрыто N задач...
Вопрос: «Кто загружен в проекте Araka?»
```SELECT ji.assignee_name, COUNT(*) as task_count FROM normalized.jira_issues ji LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key WHERE p.name ILIKE '%Araka%' AND ji.status NOT IN ('Done', 'Closed', 'Готово') AND ji.assignee_name IS NOT NULL GROUP BY ji.assignee_name ORDER BY task_count DESC LIMIT 10```
Ответ: Участники проекта и их загрузка...
Вопрос: «Story points по исполнителям в Araka»
```SELECT ji.assignee_name, SUM(ji.story_points) as total_story_points, COUNT(*) as task_count FROM normalized.jira_issues ji LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key WHERE p.name ILIKE '%Araka%' AND ji.status NOT IN ('Done', 'Closed', 'Готово') AND ji.assignee_name IS NOT NULL GROUP BY ji.assignee_name ORDER BY total_story_points DESC LIMIT 10```
Ответ: Story points по исполнителям...
Вопрос: «Сколько багов у проекта Araka?»
```SELECT p.name as project_name, COUNT(*) as bug_count FROM normalized.jira_issues ji LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key WHERE p.name ILIKE '%Araka%' AND ji.issue_type = 'Bug' AND ji.status NOT IN ('Done', 'Closed', 'Готово') GROUP BY p.name LIMIT 10```
Ответ: В проекте Araka N багов...
Вопрос: «Над какими задачами работает Alenakrash95?»
```SELECT ji.issue_key, ji.summary, ji.status, p.name as project_name FROM normalized.jira_issues ji LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key WHERE ji.assignee_name ILIKE '%Alenakrash95%' AND ji.status NOT IN ('Done', 'Closed', 'Готово') ORDER BY ji.updated_at DESC LIMIT 20```
Ответ: У Alenakrash95 N активных задач...
Вопрос: «Напиши фокус команды Araka»
Ответ: Извините, у меня нет данных о фокусе или стратегии команды. Я могу показать задачи, баги, загрузку участников и другие метрики проекта.
ВАЖНО: Всегда начинай ответ с SQL блока в markdown формате!
ВАЖНО: В ответах используй реальные названия проектов (p.name), а не ключи (project_key).
ВАЖНО: НЕ упоминай "база данных", "БД", "таблицы" в ответах пользователям.
ВАЖНО: НИКОГДА не выдумывай информацию! Если данных нет — так и скажи."""
def _normalize_name(name: str) -> str:
    """Нормализует имя для поиска (варианты имён)"""
    name_lower = name.lower()
    # Варианты имён
    name_variants = {
        'леши': 'Алексей',
        'леша': 'Алексей',
        'алекс': 'Алексей',
        'саша': 'Александр',
        'саня': 'Александр',
        'александ': 'Александр',
        'серёжа': 'Сергей',
        'сергей': 'Сергей',
        'дяша': 'Дмитрий',
        'димас': 'Дмитрий',
        'дима': 'Дмитрий',
        'вик': 'Виктор',
        'виктор': 'Виктор',
        'макс': 'Максим',
        'максим': 'Максим',
        'андрюша': 'Андрей',
        'андрей': 'Андрей',
        'оля': 'Ольга',
        'ольга': 'Ольга',
        'настя': 'Анастасия',
        'нastas': 'Анастасия',
        'катя': 'Екатерина',
        'екатерина': 'Екатерина',
        'таня': 'Татьяна',
        'татьяна': 'Татьяна',
    }

    return name_variants.get(name_lower, name.capitalize())

def _generate_sql_from_question(question: str) -> List[str]:
    """
    Программно генерирует SQL на основе вопроса пользователя.
    Это fallback если AI не смог сгенерировать SQL.
    """
    question_lower = question.lower().strip()

    # ============================================================
    # 1. Извлечение названия проекта (расширенное)
    # ============================================================
    project_name = None
    # Ищем паттерны: "в Araka", "в проекте Araka", "проекта Araka", "команды Araka", "проект Araka"
    project_patterns = [
        r'в\s+(?:проекте\s+)?([A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё0-9_.\s-]{0,40}?)(?=\s|$)',
        r'(?:проекта|проект|команды|команде)\s+([A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё0-9_.\s-]{0,40}?)(?=\s|$)',
        r'у\s+([A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё0-9_.\s-]{0,40}?)(?=\s|$)',
    ]

    for pattern in project_patterns:
        match = re.search(pattern, question_lower)
        if match:
            candidate = match.group(1).strip()
            # Убираем мусорные слова
            stop_words = ['задач', 'баг', 'проект', 'команд', 'статистик', 'отчёт', 'отчет', 
                        'дедлайн', 'срок', 'просрочен', 'участник', 'открыт', 'закрыт']
            words = candidate.split()
            words = [w for w in words if w not in stop_words]
            if words:
                project_name = ' '.join(words)
                break
    # ============================================================
    # 2. Локальное извлечение имени (более надёжное)
    # ============================================================
    def _extract_name_local(q: str) -> Optional[str]:
        q_lower = q.lower()
        
        # Паттерны для имён (включая английские логины)
        patterns = [
            r'у\s+([а-яёa-z0-9_.-]+(?:\s+[а-яёa-z0-9_.-]+){0,2})',
            r'([а-яёa-z0-9_.-]+)\s+(?:работает|занят|перегруж)',
            r'(?:работает|занят|перегруж)\s+([а-яёa-z0-9_.-]+)',
            r'над\s+чем\s+(?:работает|занят)\s+([а-яёa-z0-9_.-]+)',
            r'([а-яёa-z0-9_.-]+)\s+задач',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, q_lower)
            if match:
                raw = match.group(1).strip()
                # Убираем служебные слова
                stop_words = {'задач', 'в', 'проект', 'проекте', 'команде', 'активных'}
                words = [w for w in raw.split() if w not in stop_words]
                if words:
                    return ' '.join(words)
        return None

    name_in_question = _extract_name_local(question)

    # Нормализация имён (варианты → канонические)
    def _normalize_name(n: str) -> str:
        if not n:
            return n
        n_lower = n.lower()
        variants = {
            'алена': 'Алёна', 'алёна': 'Алёна',
            'ксения': 'Ксения', 'ксюша': 'Ксения',
            'регина': 'ReGina', 'регины': 'ReGina', 'regina': 'ReGina',
            'настя': 'Анастасия',
            'оля': 'Ольга', 'ольга': 'Ольга',
            'катя': 'Екатерина', 'екатерина': 'Екатерина',
            'леши': 'Алексей', 'леша': 'Алексей',
            'саша': 'Александр',
            'серёжа': 'Сергей', 'сергей': 'Сергей',
            'дима': 'Дмитрий',
            'макс': 'Максим', 'максим': 'Максим',
            'андрей': 'Андрей',
            'таня': 'Татьяна', 'татьяна': 'Татьяна',
        }
        if n_lower in variants:
            return variants[n_lower]
        # Для составных имён нормализуем каждое слово
        words = n.split()
        normalized = [variants.get(w.lower(), w.capitalize()) for w in words]
        return ' '.join(normalized)

    if name_in_question:
        name_in_question = _normalize_name(name_in_question)

    # ============================================================
    # 3. Генерация SQL — от специфичных блоков к общим
    # ============================================================
    # 1. Запрос на задачи конкретного человека (по имени)
    if name_in_question and ('работает' in question_lower or 'занят' in question_lower or 'задач' in question_lower):
        # Пробуем разные варианты написания имени
        name_variants = [
            name_in_question,
            name_in_question.lower(),
            name_in_question.upper(),
            name_in_question.capitalize()
        ]
        # Добавляем варианты с разными окончаниями
        if name_in_question.endswith('а') or name_in_question.endswith('я'):
            name_variants.append(name_in_question[:-1])  # Убираем окончание
        
        like_conditions = ' OR '.join([f"ji.assignee_name ILIKE '%{variant}%'" for variant in set(name_variants)])
        
        return [f"""
            SELECT ji.issue_key, ji.summary, ji.status, ji.assignee_name,
                p.name as project_name, ji.due_date, ji.story_points, ji.priority
            FROM normalized.jira_issues ji
            LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key
            WHERE ({like_conditions})
            AND ji.status NOT IN ('Done', 'Closed', 'Готово')
            ORDER BY ji.updated_at DESC
            LIMIT 20
        """]

    # 2. Баги в проекте
    if 'баг' in question_lower and project_name:
        return [f"""
            SELECT p.name as project_name, ji.project_key,
                COUNT(*) as bug_count,
                array_agg(DISTINCT ji.issue_key) as bug_keys
            FROM normalized.jira_issues ji
            LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key
            WHERE p.name ILIKE '%{project_name}%'
            AND ji.issue_type ILIKE '%Bug%'
            AND ji.status NOT IN ('Done', 'Closed', 'Готово')
            GROUP BY p.name, ji.project_key
            LIMIT 10
        """]

    # 3. Закрытые задачи в проекте (с поддержкой разных вариантов названия)
    if ('закрыт' in question_lower or 'done' in question_lower or 'closed' in question_lower) and project_name:
        # Пробуем разные варианты названия проекта
        project_variants = [
            project_name,
            project_name.replace(' - ', ' '),
            project_name.replace('-', ' '),
            project_name.lower(),
            project_name.upper(),
            project_name.capitalize()
        ]
        like_conditions = ' OR '.join([f"p.name ILIKE '%{variant}%'" for variant in set(project_variants)])
        
        return [f"""
            SELECT ji.issue_key, ji.summary, ji.status, ji.closed_at, ji.assignee_name
            FROM normalized.jira_issues ji
            LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key
            WHERE ({like_conditions})
            AND ji.status IN ('Done', 'Closed', 'Готово')
            ORDER BY ji.closed_at DESC
            LIMIT 20
        """]

    # 4. Участники проекта и их загрузка
    if ('участник' in question_lower or 'загружен' in question_lower or 'команд' in question_lower) and project_name:
        project_variants = [
            project_name,
            project_name.replace(' - ', ' '),
            project_name.replace('-', ' '),
            project_name.lower(),
            project_name.upper(),
            project_name.capitalize()
        ]
        like_conditions = ' OR '.join([f"p.name ILIKE '%{variant}%'" for variant in set(project_variants)])
        
        return [f"""
            SELECT ji.assignee_name, COUNT(*) as task_count,
                SUM(ji.story_points) as total_story_points,
                COUNT(*) FILTER (WHERE ji.issue_type = 'Bug') as bug_count,
                COUNT(*) FILTER (WHERE ji.due_date < NOW()) as overdue_count
            FROM normalized.jira_issues ji
            LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key
            WHERE ({like_conditions})
            AND ji.status NOT IN ('Done', 'Closed', 'Готово')
            AND ji.assignee_name IS NOT NULL
            GROUP BY ji.assignee_name
            ORDER BY task_count DESC
            LIMIT 10
        """]
    # --- "В работе" (In Progress) ---
    if 'в работе' in question_lower or 'in progress' in question_lower:
        if project_name:
            return [f"""
                SELECT p.name as project_name, ji.project_key,
                    COUNT(*) as in_progress_count
                FROM normalized.jira_issues ji
                LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key
                WHERE p.name ILIKE '%{project_name}%'
                AND ji.status IN ('In Progress', 'В работе')
                GROUP BY p.name, ji.project_key
                LIMIT 10
            """]
        return ["""
            SELECT p.name as project_name, ji.project_key,
                COUNT(*) as in_progress_count
            FROM normalized.jira_issues ji
            LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key
            WHERE ji.status IN ('In Progress', 'В работе')
            GROUP BY p.name, ji.project_key
            ORDER BY in_progress_count DESC
            LIMIT 10
        """]

    # --- Самый проблемный проект ---
    if 'проблемн' in question_lower or 'хуже' in question_lower:
        return ["""
            SELECT project_name, project_key, overdue_count, bug_count, old_tasks,
                (overdue_count + bug_count) as total_problems
            FROM (
                SELECT p.name as project_name, ji.project_key,
                    COUNT(*) FILTER (WHERE ji.status NOT IN ('Done', 'Closed', 'Готово')) as open_tasks,
                    COUNT(*) FILTER (WHERE ji.due_date < NOW() AND ji.status NOT IN ('Done', 'Closed', 'Готово')) as overdue_count,
                    COUNT(*) FILTER (WHERE ji.issue_type = 'Bug' AND ji.status NOT IN ('Done', 'Closed', 'Готово')) as bug_count,
                    COUNT(*) FILTER (WHERE ji.created_at < NOW() - INTERVAL '30 days' AND ji.status NOT IN ('Done', 'Closed', 'Готово')) as old_tasks
                FROM normalized.jira_issues ji
                LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key
                WHERE ji.status NOT IN ('Done', 'Closed', 'Готово')
                GROUP BY p.name, ji.project_key
            ) AS subq
            ORDER BY total_problems DESC
            LIMIT 10
        """]

    # --- Открытые задачи СПИСКОМ (покажи / список / какие) ---
    if ('покажи' in question_lower or 'список' in question_lower or 'какие' in question_lower or 'что за' in question_lower) \
            and 'задач' in question_lower and ('открыт' in question_lower or 'активн' in question_lower or project_name):
        if project_name:
            return [f"""
                SELECT ji.issue_key, ji.summary, ji.status, ji.assignee_name,
                    ji.due_date, ji.priority, p.name as project_name
                FROM normalized.jira_issues ji
                LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key
                WHERE p.name ILIKE '%{project_name}%'
                AND ji.status NOT IN ('Done', 'Closed', 'Готово')
                ORDER BY ji.updated_at DESC
                LIMIT 50
            """]
        return ["""
            SELECT ji.issue_key, ji.summary, ji.status, ji.assignee_name,
                ji.due_date, p.name as project_name
            FROM normalized.jira_issues ji
            LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key
            WHERE ji.status NOT IN ('Done', 'Closed', 'Готово')
            ORDER BY ji.updated_at DESC
            LIMIT 50
        """]

    # --- Закрытые задачи в проекте ---
    if ('закрыт' in question_lower or 'done' in question_lower or 'closed' in question_lower) \
            and ('проект' in question_lower or project_name):
        if project_name:
            return [f"""
                SELECT ji.issue_key, ji.summary, ji.status, ji.closed_at, ji.assignee_name
                FROM normalized.jira_issues ji
                LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key
                WHERE p.name ILIKE '%{project_name}%'
                AND ji.status IN ('Done', 'Closed', 'Готово')
                ORDER BY ji.closed_at DESC
                LIMIT 20
            """]
        return ["""
            SELECT ji.issue_key, ji.summary, ji.status, ji.closed_at, p.name as project_name
            FROM normalized.jira_issues ji
            LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key
            WHERE ji.status IN ('Done', 'Closed', 'Готово')
            ORDER BY ji.closed_at DESC
            LIMIT 20
        """]

    # --- Участники / загрузка / команда ---
    if ('участник' in question_lower or 'загружен' in question_lower or 'команд' in question_lower
            or 'входит в' in question_lower or 'работает в' in question_lower or 'нагрузк' in question_lower) \
            and ('проект' in question_lower or project_name):
        if project_name:
            return [f"""
                SELECT ji.assignee_name, COUNT(*) as task_count,
                    SUM(ji.story_points) as total_story_points
                FROM normalized.jira_issues ji
                LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key
                WHERE p.name ILIKE '%{project_name}%'
                AND ji.status NOT IN ('Done', 'Closed', 'Готово')
                AND ji.assignee_name IS NOT NULL
                GROUP BY ji.assignee_name
                ORDER BY task_count DESC
                LIMIT 10
            """]
        return ["""
            SELECT ji.assignee_name, COUNT(*) as task_count
            FROM normalized.jira_issues ji
            WHERE ji.status NOT IN ('Done', 'Closed', 'Готово')
            AND ji.assignee_name IS NOT NULL
            GROUP BY ji.assignee_name
            ORDER BY task_count DESC
            LIMIT 10
        """]

    # --- Кто перегружен ---
    if 'перегруж' in question_lower:
        if project_name:
            return [f"""
                SELECT ji.assignee_name, COUNT(*) as task_count,
                    SUM(ji.story_points) as total_story_points
                FROM normalized.jira_issues ji
                LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key
                WHERE p.name ILIKE '%{project_name}%'
                AND ji.status NOT IN ('Done', 'Closed', 'Готово')
                AND ji.assignee_name IS NOT NULL
                GROUP BY ji.assignee_name
                ORDER BY task_count DESC
                LIMIT 5
            """]
        return ["""
            SELECT ji.assignee_name, COUNT(*) as task_count
            FROM normalized.jira_issues ji
            WHERE ji.status NOT IN ('Done', 'Closed', 'Готово')
            AND ji.assignee_name IS NOT NULL
            GROUP BY ji.assignee_name
            ORDER BY task_count DESC
            LIMIT 5
        """]

    # --- Кто свободен / у кого нет задач ---
    if ('свободн' in question_lower or 'нет активн' in question_lower or 'не загруж' in question_lower):
        return ["""
            SELECT assignee_name, 0 as task_count
            FROM (
                SELECT DISTINCT assignee_name
                FROM normalized.jira_issues
                WHERE assignee_name IS NOT NULL
            ) AS all_users
            WHERE assignee_name NOT IN (
                SELECT DISTINCT assignee_name
                FROM normalized.jira_issues
                WHERE status NOT IN ('Done', 'Closed', 'Готово')
                AND assignee_name IS NOT NULL
            )
            LIMIT 20
        """]

    # --- Story points по команде/исполнителям ---
    if 'story' in question_lower and 'point' in question_lower and ('исполнител' in question_lower or 'команд' in question_lower or 'подсчитай' in question_lower):
        if project_name:
            return [f"""
                SELECT ji.assignee_name,
                    SUM(ji.story_points) as total_story_points,
                    COUNT(*) as task_count
                FROM normalized.jira_issues ji
                LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key
                WHERE p.name ILIKE '%{project_name}%'
                AND ji.status NOT IN ('Done', 'Closed', 'Готово')
                AND ji.assignee_name IS NOT NULL
                GROUP BY ji.assignee_name
                ORDER BY total_story_points DESC
                LIMIT 10
            """]
        return ["""
            SELECT ji.assignee_name,
                SUM(ji.story_points) as total_story_points,
                COUNT(*) as task_count
            FROM normalized.jira_issues ji
            WHERE ji.status NOT IN ('Done', 'Closed', 'Готово')
            AND ji.assignee_name IS NOT NULL
            GROUP BY ji.assignee_name
            ORDER BY total_story_points DESC
            LIMIT 10
        """]

    # --- Story points одной задачи ---
    if 'story' in question_lower and 'point' in question_lower:
        if project_name:
            return [f"""
                SELECT ji.issue_key, ji.summary, ji.story_points, p.name as project_name
                FROM normalized.jira_issues ji
                LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key
                WHERE p.name ILIKE '%{project_name}%'
                AND ji.story_points IS NOT NULL
                ORDER BY ji.story_points DESC
                LIMIT 20
            """]
        return ["""
            SELECT ji.issue_key, ji.summary, ji.story_points, p.name as project_name
            FROM normalized.jira_issues ji
            LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key
            WHERE ji.story_points IS NOT NULL
            ORDER BY ji.story_points DESC
            LIMIT 20
        """]

    # --- Просроченные задачи ---
    if 'просроченн' in question_lower:
        if project_name:
            # Если просят СПИСОК просроченных
            if 'какие' in question_lower or 'список' in question_lower or 'покажи' in question_lower:
                return [f"""
                    SELECT ji.issue_key, ji.summary, ji.assignee_name, ji.due_date,
                        p.name as project_name,
                        (NOW()::date - ji.due_date::date) as overdue_days
                    FROM normalized.jira_issues ji
                    LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key
                    WHERE p.name ILIKE '%{project_name}%'
                    AND ji.due_date < NOW()
                    AND ji.status NOT IN ('Done', 'Closed', 'Готово')
                    ORDER BY ji.due_date ASC
                    LIMIT 20
                """]
            # Иначе — счётчик
            return [f"""
                SELECT p.name as project_name, ji.project_key,
                    COUNT(*) as overdue_count
                FROM normalized.jira_issues ji
                LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key
                WHERE p.name ILIKE '%{project_name}%'
                AND ji.due_date < NOW()
                AND ji.status NOT IN ('Done', 'Closed', 'Готово')
                GROUP BY p.name, ji.project_key
                LIMIT 10
            """]
        # Топ проектов по просроченным
        return ["""
            SELECT p.name as project_name, ji.project_key,
                COUNT(*) as overdue_count
            FROM normalized.jira_issues ji
            LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key
            WHERE ji.due_date < NOW() AND ji.status NOT IN ('Done', 'Closed', 'Готово')
            GROUP BY p.name, ji.project_key
            ORDER BY overdue_count DESC
            LIMIT 10
        """]

    # --- Топ проектов по багам ---
    if 'топ' in question_lower and 'баг' in question_lower:
        return ["""
            SELECT p.name as project_name, ji.project_key,
                COUNT(*) as bug_count
            FROM normalized.jira_issues ji
            LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key
            WHERE ji.issue_type = 'Bug'
            AND ji.status NOT IN ('Done', 'Closed', 'Готово')
            GROUP BY p.name, ji.project_key
            ORDER BY bug_count DESC
            LIMIT 10
        """]

    # --- Баги в проекте ---
    if 'баг' in question_lower and ('проект' in question_lower or project_name or 'открыт' in question_lower or 'есть ли' in question_lower):
        if project_name:
            # Если просят СПИСОК багов
            if 'какие' in question_lower or 'список' in question_lower or 'покажи' in question_lower:
                return [f"""
                    SELECT ji.issue_key, ji.summary, ji.assignee_name, ji.priority,
                        ji.status, p.name as project_name
                    FROM normalized.jira_issues ji
                    LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key
                    WHERE p.name ILIKE '%{project_name}%'
                    AND ji.issue_type = 'Bug'
                    AND ji.status NOT IN ('Done', 'Closed', 'Готово')
                    ORDER BY ji.priority DESC, ji.created_at DESC
                    LIMIT 20
                """]
            # Иначе — счётчик
            return [f"""
                SELECT p.name as project_name, ji.project_key,
                    COUNT(*) as bug_count
                FROM normalized.jira_issues ji
                LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key
                WHERE p.name ILIKE '%{project_name}%'
                AND ji.issue_type = 'Bug'
                AND ji.status NOT IN ('Done', 'Closed', 'Готово')
                GROUP BY p.name, ji.project_key
                LIMIT 10
            """]
        return ["""
            SELECT p.name as project_name, ji.project_key,
                COUNT(*) as bug_count
            FROM normalized.jira_issues ji
            LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key
            WHERE ji.issue_type = 'Bug' AND ji.status NOT IN ('Done', 'Closed', 'Готово')
            GROUP BY p.name, ji.project_key
            ORDER BY bug_count DESC
            LIMIT 10
        """]

    # --- Задачи конкретного человека (по имени) ---
    if name_in_question:
        # Если просят СПИСОК задач
        if 'список' in question_lower or 'какие' in question_lower or 'над чем' in question_lower or 'чем зан' in question_lower or 'у кого' in question_lower:
            return [f"""
                SELECT ji.issue_key, ji.summary, ji.status, ji.assignee_name,
                    p.name as project_name, ji.due_date, ji.story_points, ji.priority
                FROM normalized.jira_issues ji
                LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key
                WHERE ji.assignee_name ILIKE '%{name_in_question}%'
                AND ji.status NOT IN ('Done', 'Closed', 'Готово')
                ORDER BY ji.updated_at DESC
                LIMIT 20
            """]
        # Перегружен ли конкретный человек
        if 'перегруж' in question_lower:
            return [f"""
                SELECT ji.assignee_name, COUNT(*) as task_count,
                    SUM(ji.story_points) as total_story_points
                FROM normalized.jira_issues ji
                WHERE ji.assignee_name ILIKE '%{name_in_question}%'
                AND ji.status NOT IN ('Done', 'Closed', 'Готово')
                GROUP BY ji.assignee_name
                LIMIT 1
            """]
        # По умолчанию — список задач
        return [f"""
            SELECT ji.issue_key, ji.summary, ji.status, ji.assignee_name,
                p.name as project_name, ji.due_date, ji.story_points
            FROM normalized.jira_issues ji
            LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key
            WHERE ji.assignee_name ILIKE '%{name_in_question}%'
            AND ji.status NOT IN ('Done', 'Closed', 'Готово')
            ORDER BY ji.updated_at DESC
            LIMIT 20
        """]

    # --- "У кого сколько задач" / "У кого больше всего" ---
    if 'у кого' in question_lower and 'задач' in question_lower:
        if project_name:
            return [f"""
                SELECT ji.assignee_name, COUNT(*) as task_count
                FROM normalized.jira_issues ji
                LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key
                WHERE p.name ILIKE '%{project_name}%'
                AND ji.status NOT IN ('Done', 'Closed', 'Готово')
                GROUP BY ji.assignee_name
                ORDER BY task_count DESC
                LIMIT 10
            """]
        return ["""
            SELECT ji.assignee_name, COUNT(*) as task_count
            FROM normalized.jira_issues ji
            WHERE ji.status NOT IN ('Done', 'Closed', 'Готово')
            GROUP BY ji.assignee_name
            ORDER BY task_count DESC
            LIMIT 10
        """]

    # --- "У X какие задачи" (без явного имени в начале, но есть "у") ---
    if 'у' in question_lower and ('задач' in question_lower or 'task' in question_lower):
        return ["""
            SELECT ji.assignee_name,
                COUNT(*) as task_count,
                COUNT(*) FILTER (WHERE ji.issue_type = 'Bug') as bug_count
            FROM normalized.jira_issues ji
            WHERE ji.status NOT IN ('Done', 'Closed', 'Готово')
            GROUP BY ji.assignee_name
            ORDER BY task_count DESC
            LIMIT 10
        """]

    # --- Pull Requests ---
    if 'pr' in question_lower or 'pull' in question_lower or 'пул' in question_lower:
        if project_name:
            # Открытые PR
            if 'открыт' in question_lower:
                return [f"""
                    SELECT pr.pr_id, pr.title, pr.author_login, pr.created_at, pr.state
                    FROM normalized.github_pull_requests pr
                    WHERE pr.title ILIKE '%{project_name}%'
                    AND pr.state = 'open'
                    ORDER BY pr.created_at DESC
                    LIMIT 20
                """]
            # Закрытые PR
            if 'закрыт' in question_lower:
                return [f"""
                    SELECT pr.pr_id, pr.title, pr.author_login, pr.created_at, pr.merged
                    FROM normalized.github_pull_requests pr
                    WHERE pr.title ILIKE '%{project_name}%'
                    AND pr.state = 'closed'
                    ORDER BY pr.created_at DESC
                    LIMIT 20
                """]
            # Все PR — статистика
            return [f"""
                SELECT pr.state, COUNT(*) as count
                FROM normalized.github_pull_requests pr
                WHERE pr.title ILIKE '%{project_name}%'
                GROUP BY pr.state
                LIMIT 10
            """]
        # Общие PR
        if 'открыт' in question_lower:
            return ["""
                SELECT pr.pr_id, pr.title, pr.author_login, pr.created_at
                FROM normalized.github_pull_requests pr
                WHERE pr.state = 'open'
                ORDER BY pr.created_at DESC
                LIMIT 20
            """]
        return ["""
            SELECT pr.state, COUNT(*) as count
            FROM normalized.github_pull_requests pr
            GROUP BY pr.state
            LIMIT 10
        """]

    # --- Коммиты / Git / активность в репозитории ---
    if ('коммит' in question_lower or 'активност' in question_lower
            or 'репозитори' in question_lower or 'git' in question_lower
            or 'статистик' in question_lower and 'git' in question_lower):
        if project_name:
            return [f"""
                SELECT c.author_login, COUNT(*) as commit_count,
                    SUM(c.additions) as total_additions,
                    SUM(c.deletions) as total_deletions,
                    MAX(c.committed_at) as last_commit
                FROM normalized.github_commits c
                WHERE c.message ILIKE '%{project_name}%'
                GROUP BY c.author_login
                ORDER BY commit_count DESC
                LIMIT 10
            """]
        return ["""
            SELECT c.author_login, COUNT(*) as commit_count,
                SUM(c.additions) as total_additions,
                SUM(c.deletions) as total_deletions
            FROM normalized.github_commits c
            GROUP BY c.author_login
            ORDER BY commit_count DESC
            LIMIT 10
        """]

    # --- Дедлайны / сроки / на этой неделе ---
    if ('дедлайн' in question_lower or 'срок' in question_lower
            or 'на этой неделе' in question_lower or 'на неделю' in question_lower
            or 'ближайш' in question_lower):
        if project_name:
            return [f"""
                SELECT ji.issue_key, ji.summary, ji.assignee_name, ji.due_date,
                    ji.priority, p.name as project_name
                FROM normalized.jira_issues ji
                LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key
                WHERE p.name ILIKE '%{project_name}%'
                AND ji.due_date BETWEEN NOW() AND NOW() + INTERVAL '7 days'
                AND ji.status NOT IN ('Done', 'Closed', 'Готово')
                ORDER BY ji.due_date ASC
                LIMIT 20
            """]
        return ["""
            SELECT ji.issue_key, ji.summary, ji.assignee_name, ji.due_date,
                ji.priority, p.name as project_name
            FROM normalized.jira_issues ji
            LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key
            WHERE ji.due_date BETWEEN NOW() AND NOW() + INTERVAL '7 days'
            AND ji.status NOT IN ('Done', 'Closed', 'Готово')
            ORDER BY ji.due_date ASC
            LIMIT 20
        """]

    # --- Отчёт по проекту ---
    if 'отчёт' in question_lower or 'отчет' in question_lower or 'статистик' in question_lower:
        if project_name:
            return [f"""
                SELECT p.name as project_name,
                    COUNT(*) as total_tasks,
                    COUNT(*) FILTER (WHERE ji.status NOT IN ('Done', 'Closed', 'Готово')) as open_tasks,
                    COUNT(*) FILTER (WHERE ji.status IN ('Done', 'Closed', 'Готово')) as closed_tasks,
                    COUNT(*) FILTER (WHERE ji.due_date < NOW() AND ji.status NOT IN ('Done', 'Closed', 'Готово')) as overdue,
                    COUNT(*) FILTER (WHERE ji.issue_type = 'Bug') as bugs,
                    COALESCE(SUM(ji.story_points), 0) as total_story_points
                FROM normalized.jira_issues ji
                LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key
                WHERE p.name ILIKE '%{project_name}%'
                GROUP BY p.name
                LIMIT 1
            """]
        return ["""
            SELECT p.name as project_name,
                COUNT(*) as total_tasks,
                COUNT(*) FILTER (WHERE ji.status NOT IN ('Done', 'Closed', 'Готово')) as open_tasks,
                COUNT(*) FILTER (WHERE ji.status IN ('Done', 'Closed', 'Готово')) as closed_tasks,
                COUNT(*) FILTER (WHERE ji.due_date < NOW() AND ji.status NOT IN ('Done', 'Closed', 'Готово')) as overdue,
                COUNT(*) FILTER (WHERE ji.issue_type = 'Bug') as bugs
            FROM normalized.jira_issues ji
            LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key
            GROUP BY p.name
            ORDER BY open_tasks DESC
            LIMIT 10
        """]

    # --- Сравнение проектов ---
    if 'сравни' in question_lower or 'сравнени' in question_lower:
        projects = re.findall(r'(?:проект(?:ом)?|с)\s+([a-zа-яё0-9_.-]+)', question_lower)
        if len(projects) >= 2:
            proj1, proj2 = projects[0], projects[1]
            return [f"""
                SELECT p.name as project_name,
                    COUNT(*) as total_tasks,
                    COUNT(*) FILTER (WHERE ji.status NOT IN ('Done', 'Closed', 'Готово')) as open_tasks,
                    COUNT(*) FILTER (WHERE ji.due_date < NOW() AND ji.status NOT IN ('Done', 'Closed', 'Готово')) as overdue,
                    COUNT(*) FILTER (WHERE ji.issue_type = 'Bug') as bugs
                FROM normalized.jira_issues ji
                LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key
                WHERE p.name ILIKE '%{proj1}%' OR p.name ILIKE '%{proj2}%'
                GROUP BY p.name
                LIMIT 10
            """]

    # --- Все проекты ---
    if 'проект' in question_lower and ('всё' in question_lower or 'все' in question_lower or 'покажи' in question_lower or 'список' in question_lower or 'мои' in question_lower or 'активн' in question_lower):
        return ["SELECT key, name, is_active FROM core.projects WHERE is_active = true LIMIT 100"]

    # --- Считаем задачи (общий случай) ---
    if 'сколько' in question_lower and 'задач' in question_lower:
        if project_name:
            return [f"""
                SELECT p.name as project_name, ji.project_key,
                    COUNT(*) as total_open,
                    COUNT(*) FILTER (WHERE ji.due_date < NOW()) as overdue,
                    COUNT(*) FILTER (WHERE ji.issue_type = 'Bug') as bugs,
                    COALESCE(SUM(ji.story_points), 0) as total_story_points
                FROM normalized.jira_issues ji
                LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key
                WHERE p.name ILIKE '%{project_name}%'
                AND ji.status NOT IN ('Done', 'Closed', 'Готово')
                GROUP BY p.name, ji.project_key
                LIMIT 10
            """]
        return ["""
            SELECT p.name as project_name, ji.project_key,
                COUNT(*) as total_open,
                COUNT(*) FILTER (WHERE ji.due_date < NOW()) as overdue,
                COUNT(*) FILTER (WHERE ji.issue_type = 'Bug') as bugs
            FROM normalized.jira_issues ji
            LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key
            WHERE ji.status NOT IN ('Done', 'Closed', 'Готово')
            GROUP BY p.name, ji.project_key
            ORDER BY total_open DESC
            LIMIT 10
        """]
    # --- "Список задач проекта" ---
    if 'список' in question_lower and 'задач' in question_lower and project_name:
        return [f"""
            SELECT ji.issue_key, ji.summary, ji.status, ji.assignee_name, ji.due_date
            FROM normalized.jira_issues ji
            LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key
            WHERE p.name ILIKE '%{project_name}%'
            ORDER BY ji.updated_at DESC
            LIMIT 50
        """]

    # --- "Есть ли просроченные задачи" ---
    if 'есть ли' in question_lower and 'просроченн' in question_lower:
        if project_name:
            return [f"""
                SELECT COUNT(*) as has_overdue
                FROM normalized.jira_issues ji
                LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key
                WHERE p.name ILIKE '%{project_name}%'
                AND ji.due_date < NOW()
                AND ji.status NOT IN ('Done', 'Closed', 'Готово')
            """]

    # --- "Что происходит в проекте" (общая сводка) ---
    if 'что происходит' in question_lower or 'что с проектом' in question_lower:
        if project_name:
            return [f"""
                SELECT 
                    COUNT(*) FILTER (WHERE ji.status NOT IN ('Done', 'Closed', 'Готово')) as open_tasks,
                    COUNT(*) FILTER (WHERE ji.status IN ('Done', 'Closed', 'Готово')) as closed_tasks,
                    COUNT(*) FILTER (WHERE ji.due_date < NOW() AND ji.status NOT IN ('Done', 'Closed', 'Готово')) as overdue,
                    COUNT(*) FILTER (WHERE ji.issue_type = 'Bug') as bugs
                FROM normalized.jira_issues ji
                LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key
                WHERE p.name ILIKE '%{project_name}%'
            """]

    # --- "Сколько всего задач" (без фильтра по статусу) ---
    if 'всего задач' in question_lower or 'всего' in question_lower and 'задач' in question_lower:
        if project_name:
            return [f"""
                SELECT COUNT(*) as total_tasks
                FROM normalized.jira_issues ji
                LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key
                WHERE p.name ILIKE '%{project_name}%'
            """]
    # --- По умолчанию - ничего ---
    return []
