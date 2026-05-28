# Chat Bot API Documentation

## Описание

Умный чат с AI для аналитики разработки. AI понимает вопросы на естественном языке, самостоятельно решает, какие данные нужны, и формулирует ответ.

## Безопасность

- **Только SELECT запросы** — запрещены INSERT/UPDATE/DELETE/DROP/ALTER
- **Разрешённые таблицы** — только таблицы из списка ALLOWED_TABLES
- **Лимит строк** — максимум 100 строк в ответе (автоматически добавляется LIMIT)
- **Логирование** — все SQL запросы логируются

## Разрешённые таблицы

```
identity.users
core.projects
core.user_projects
normalized.jira_issues
normalized.issue_changelog
normalized.project_status_mappings
normalized.github_issues
normalized.github_commits
normalized.github_pull_requests
```

## API Endpoints

### 1. Базовый чат с AI

**POST** `/chat/completion` или `/api/chat/completion`

Запрос:
```json
{
  "message": "Сколько задач у Ивана?",
  "session_id": "uuid",
  "history": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}
```

Ответ:
```json
{
  "answer": "У Ивана 7 активных задач",
  "session_id": "uuid",
  "metadata": {
    "sql_queries": ["SELECT ..."],
    "tool_calls": ["execute_sql"]
  }
}
```

### 2. Улучшенный чат с AI (рекомендуется)

**POST** `/chat/ai-completion` или `/api/chat/ai-completion`

AI автоматически определяет, какие SQL запросы нужны, и выполняет их.

### 3. Выполнение SQL запроса напрямую

**POST** `/chat/tools/execute-sql` или `/api/chat/tools/execute-sql`

Запрос:
```json
{
  "sql": "SELECT project_key, COUNT(*) FROM normalized.jira_issues GROUP BY project_key LIMIT 10"
}
```

Ответ:
```json
{
  "success": true,
  "data": [
    {"project_key": "PROJ", "count": 42}
  ],
  "row_count": 1
}
```

### 4. Вызов инструментов

**POST** `/chat/tools/call` или `/api/chat/tools/call`

Запрос:
```json
{
  "tool_name": "get_project_metrics",
  "params": {
    "project_key": "PROJ"
  }
}
```

Доступные инструменты:
- `execute_sql` — выполнить SQL запрос
- `get_project_metrics` — получить метрики проекта
- `get_user_workload` — получить загрузку пользователя

### 5. Получение списка разрешённых таблиц

**GET** `/chat/allowed-tables` или `/api/chat/allowed-tables`

Ответ:
```json
{
  "tables": ["identity.users", "core.projects", ...],
  "description": "Only SELECT queries allowed. Max 100 rows."
}
```

## Примеры использования

### Сколько задач у Ивана?

```
POST /chat/ai-completion
{
  "message": "Сколько задач у Ивана?"
}
```

### Какой проект самый проблемный?

```
POST /chat/ai-completion
{
  "message": "Какой проект самый проблемный?"
}
```

### Покажи просроченные задачи

```
POST /chat/ai-completion
{
  "message": "Покажи просроченные задачи"
}
```

### Загрузка команды

```
POST /chat/ai-completion
{
  "message": "Какая загрузка у команды?"
}
```

## Фронтенд

Компонент ChatBot находится в `electron-app/src/renderer/src/components/MiniPanel/ChatBot/ChatBot.tsx`

### Особенности:

1. **Работа с реальным API** — использует `chatAiCompletion`
2. **Сохранение истории** — localStorage для сохранения сессии
3. **Индикаторы загрузки** — Spin во время обработки
4. **Обработка ошибок** — Alert с сообщением об ошибке
5. **SQL Debug режим** — кнопка SQL для отображения выполненных запросов
6. **Очистка истории** — кнопка "Очистить"

## Конфигурация

Переменные окружения:
```
OPENROUTER_API_KEY=your_api_key
OPENROUTER_MODEL=openai/gpt-4o-mini
```

## Логи

Все SQL запросы логируются через logger:
- `Executing SQL: ...` — перед выполнением
- `SQL returned X rows` — после выполнения
- `SQL validation failed: ...` — при ошибке валидации

## Расширение функциональности

Для добавления новых инструментов:
1. Добавьте метод в `ChatToolService` (chat_service.py)
2. Добавьте обработку в `call_tool` эндпоинт (chat_endpoints.py)
3. Обновите системный промпт в `_build_system_prompt_with_schema`
