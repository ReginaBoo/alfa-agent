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
from app.services.ai.providers.alphabank_provider import AlphaBankProvider
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

def _get_ai_provider() -> AlphaBankProvider:
    """Создаёт экземпляр AI провайдера"""
    return AlphaBankProvider(
        api_key=settings.ALPHABANK_API_KEY,
        model=settings.ALPHABANK_MODEL,
        api_url=settings.ALPHABANK_API_URL
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
                {"role": "system", "content": "Ты — аналитический ассистент Alpha Agent. Отвечай кратко и по существу."},
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
        return "Данные не найдены."
    
    question_lower = question.lower()
    
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
    
    # Баги
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
    
    # Задачи у человека
    if 'у' in question_lower and ('задач' in question_lower or 'task' in question_lower):
        if 'assignee_name' in results[0] or 'name' in results[0]:
            name = results[0].get('assignee_name') or results[0].get('name', 'Неизвестно')
            count = results[0].get('count', results[0].get('task_count', 0))
            bugs = results[0].get('bug_count', 0)
            overdue = results[0].get('overdue_count', 0)
            
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

ПРИМЕР ПРАВИЛЬНОГО ОТВЕТА:

```sql
SELECT p.name as project_name, ji.project_key, COUNT(*) as open_tasks FROM normalized.jira_issues ji LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key WHERE ji.status NOT IN ('Done', 'Closed', 'Готово') GROUP BY p.name, ji.project_key LIMIT 10
```

Анализирую данные по проектам...

============================================================
ПРИМЕРЫ ВОПРОСОВ И ОТВЕТОВ:

Вопрос: «Привет»
Ответ: Здравствуйте! Чем я могу вам помочь сегодня?

Вопрос: «Какой проект самый проблемный?»
```sql
SELECT project_name, project_key, overdue, bugs, (overdue + bugs) as total_problems FROM (SELECT p.name as project_name, ji.project_key, COUNT(*) FILTER (WHERE ji.due_date < NOW()) as overdue, COUNT(*) FILTER (WHERE ji.issue_type = 'Bug') as bugs FROM normalized.jira_issues ji LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key WHERE ji.status NOT IN ('Done', 'Closed', 'Готово') GROUP BY p.name, ji.project_key) AS subq ORDER BY total_problems DESC LIMIT 10
```
Ответ: Топ проектов с наибольшим количеством проблем...

Вопрос: «Сколько просроченных задач?»
```sql
SELECT p.name as project_name, ji.project_key, COUNT(*) as overdue_count FROM normalized.jira_issues ji LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key WHERE ji.due_date < NOW() AND ji.status NOT IN ('Done', 'Closed', 'Готово') GROUP BY p.name, ji.project_key ORDER BY overdue_count DESC LIMIT 10
```
Ответ: Топ проектов по просроченным задачам...

Вопрос: «Где много багов?»
```sql
SELECT p.name as project_name, ji.project_key, COUNT(*) as bug_count FROM normalized.jira_issues ji LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key WHERE ji.issue_type = 'Bug' AND ji.status NOT IN ('Done', 'Closed', 'Готово') GROUP BY p.name, ji.project_key ORDER BY bug_count DESC LIMIT 10
```
Ответ: Проекты с наибольшим количеством багов...

Вопрос: «Сколько задач у Ивана?»
```sql
SELECT ji.assignee_name, COUNT(*) as task_count FROM normalized.jira_issues ji WHERE ji.assignee_name LIKE '%Иван%' AND ji.status NOT IN ('Done', 'Closed', 'Готово') GROUP BY ji.assignee_name LIMIT 10
```
Ответ: У Ивана X активных задач...

Вопрос: «Покажи все проекты?»
```sql
SELECT key, name, is_active FROM core.projects WHERE is_active = true LIMIT 100
```
Ответ: Вот список проектов...

ВАЖНО: Всегда начинай ответ с SQL блока в markdown формате!
ВАЖНО: В ответах используй реальные названия проектов (p.name), а не ключи (project_key).
ВАЖНО: НЕ упоминай "база данных", "БД", "таблицы" в ответах пользователям."""



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
    question_lower = question.lower()
    
    # Проблемный проект — детальный запрос с реальными названиями
    if 'проблемн' in question_lower or 'хуже' in question_lower:
        return [
            """SELECT project_name, project_key, overdue_count, bug_count, old_tasks,
                (overdue_count + bug_count) as total_problems
            FROM (
                SELECT 
                    p.name as project_name, 
                    ji.project_key,
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
            LIMIT 10"""
        ]
    
    # Просроченные задачи — показываем топ проектов
    if 'просроченн' in question_lower:
        return [
            """SELECT 
                p.name as project_name,
                ji.project_key,
                COUNT(*) as overdue_count
            FROM normalized.jira_issues ji
            LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key
            WHERE ji.due_date < NOW() AND ji.status NOT IN ('Done', 'Closed', 'Готово')
            GROUP BY p.name, ji.project_key
            ORDER BY overdue_count DESC
            LIMIT 10"""
        ]
    
    # Баги
    if 'баг' in question_lower:
        return [
            """SELECT 
                p.name as project_name,
                ji.project_key,
                COUNT(*) as bug_count
            FROM normalized.jira_issues ji
            LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key
            WHERE ji.issue_type = 'Bug' AND ji.status NOT IN ('Done', 'Closed', 'Готово')
            GROUP BY p.name, ji.project_key
            ORDER BY bug_count DESC
            LIMIT 10"""
        ]
    
    # Задачи у человека — с нормализацией имён
    if 'у' in question_lower and ('задач' in question_lower or 'task' in question_lower):
        # Пытаемся извлечь имя
        name_match = re.search(r'у\s+([а-яёa-z0-9_.-]+)', question_lower)
        if name_match:
            raw_name = name_match.group(1)
            normalized_name = _normalize_name(raw_name)
            return [
                f"""SELECT 
                    ji.assignee_name,
                    COUNT(*) as task_count,
                    COUNT(*) FILTER (WHERE ji.issue_type = 'Bug') as bug_count,
                    COUNT(*) FILTER (WHERE ji.due_date < NOW()) as overdue_count
                FROM normalized.jira_issues ji
                WHERE ji.assignee_name ILIKE '%{normalized_name}%' AND ji.status NOT IN ('Done', 'Closed', 'Готово')
                GROUP BY ji.assignee_name
                LIMIT 10"""
            ]
        return [
            """SELECT 
                ji.assignee_name,
                COUNT(*) as task_count,
                COUNT(*) FILTER (WHERE ji.issue_type = 'Bug') as bug_count
            FROM normalized.jira_issues ji
            WHERE ji.status NOT IN ('Done', 'Closed', 'Готово')
            GROUP BY ji.assignee_name
            ORDER BY task_count DESC
            LIMIT 10"""
        ]
    
    # Запрос "сколько задач у..." (без "у")
    if 'сколько' in question_lower and 'задач' in question_lower:
        name_match = re.search(r'у\s+([а-яёa-z0-9_.-]+)', question_lower)
        if name_match:
            raw_name = name_match.group(1)
            normalized_name = _normalize_name(raw_name)
            return [
                f"""SELECT 
                    ji.assignee_name,
                    COUNT(*) as task_count,
                    COUNT(*) FILTER (WHERE ji.issue_type = 'Bug') as bug_count
                FROM normalized.jira_issues ji
                WHERE ji.assignee_name ILIKE '%{normalized_name}%' AND ji.status NOT IN ('Done', 'Closed', 'Готово')
                GROUP BY ji.assignee_name
                LIMIT 10"""
            ]
        # Если без имени — показываем топ проектов по задачам
        return [
            """SELECT 
                p.name as project_name,
                ji.project_key,
                COUNT(*) as total_open,
                COUNT(*) FILTER (WHERE ji.due_date < NOW()) as overdue,
                COUNT(*) FILTER (WHERE ji.issue_type = 'Bug') as bugs
            FROM normalized.jira_issues ji
            LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key
            WHERE ji.status NOT IN ('Done', 'Closed', 'Готово')
            GROUP BY p.name, ji.project_key
            ORDER BY total_open DESC
            LIMIT 10"""
        ]
    
    # Все проекты
    if 'проект' in question_lower and ('всё' in question_lower or 'все' in question_lower or 'покажи' in question_lower):
        return [
            "SELECT key, name, is_active FROM core.projects WHERE is_active = true LIMIT 100"
        ]
    
    # Считаем задачи
    if 'сколько' in question_lower and 'задач' in question_lower:
        return [
            """SELECT 
                p.name as project_name,
                ji.project_key,
                COUNT(*) as total_open,
                COUNT(*) FILTER (WHERE ji.due_date < NOW()) as overdue,
                COUNT(*) FILTER (WHERE ji.issue_type = 'Bug') as bugs
            FROM normalized.jira_issues ji
            LEFT JOIN core.projects p ON p.jira_project_key = ji.project_key
            WHERE ji.status NOT IN ('Done', 'Closed', 'Готово')
            GROUP BY p.name, ji.project_key
            ORDER BY total_open DESC
            LIMIT 10"""
        ]
    
    # По умолчанию - ничего
    return []


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
