# E2E Тесты с Интерактивной Авторизацией

## 📋 Описание

`test_e2e_with_auth.py` — E2E тесты с реальной авторизацией через OAuth и реальными данными из внешних сервисов (Jira, GitHub).

### Отличие от `test_e2e_full_cycle.py`

| Характеристика | `test_e2e_full_cycle.py` | `test_e2e_with_auth.py` |
|----------------|--------------------------|-------------------------|
| Авторизация | Моки/опционально | **Интерактивная OAuth** |
| Данные | Автоматические тестовые | **Реальные из Jira/GitHub** |
| Сессия | Не требуется | **Обязательна** |
| Ввод пользователя | Нет | **Требует Enter после login** |
| Очистка | Автоматическая | **Опциональная** |

---

## 🚀 Запуск

### Через Docker Compose

```bash
# Обязательно с флагом -s для интерактивного ввода
docker-compose exec backend pytest tests/test_e2e_with_auth.py -v -s
```

### Локально

```bash
cd backend
pytest tests/test_e2e_with_auth.py -v -s
```

### С фильтрацией тестов

```bash
# Только тесты с авторизацией
pytest tests/test_e2e_with_auth.py -v -s -m "requires_auth"

# Без интерактивных тестов (пропустить)
pytest tests/test_e2e_with_auth.py -v -s -k "not cleanup"
```

---

## 🔄 Процесс авторизации

### Шаг 1: Запуск тестов

```bash
docker-compose exec backend pytest tests/test_e2e_with_auth.py -v -s
```

### Шаг 2: Проверка сессии

Тесты проверяют наличие активной сессии в БД:

```
======================================================================
🔐 E2E AUTHENTICATION SETUP
======================================================================

✅ Found active session for user: John Doe (john@example.com)
   Session created: 2024-01-15 14:30:00
   Session expires: 2024-01-16 14:30:00
   Client type: web

Use this session? [Y/n]: 
```

**Варианты:**
- `Y` или `Enter` — использовать существующую сессию
- `n` — начать новую авторизацию

### Шаг 3: Если сессии нет

```
⚠️  No active session found.

📋 AUTHENTICATION REQUIRED
----------------------------------------------------------------------

1. Open this URL in your browser:
   http://localhost:8000/auth/login

2. Complete OAuth login with Atlassian/GitHub

3. Return here and press Enter when ready...
----------------------------------------------------------------------

Press Enter after successful login...
```

**Действия пользователя:**
1. Открыть ссылку в браузере
2. Выполнить OAuth login (Atlassian или GitHub)
3. Вернуться в терминал и нажать `Enter`

### Шаг 4: Ожидание сессии

```
⏳ Waiting for session creation...
   Waiting... (0/300s)
   Waiting... (5/300s)
   Waiting... (10/300s)

✅ Session created!
   User: John Doe (john@example.com)
   Session ID: abc123def456...
```

### Шаг 5: Запуск тестов

После авторизации все тесты выполняются с реальными данными:

```
======================================================================
🔍 STEP 1: Health Check (authenticated)
======================================================================

   Backend status: healthy
   ✅ PostgreSQL: connected
   ✅ TimescaleDB: connected
   ⚠️  Redis: connected

   🎉 STEP 1 PASSED
```

---

## 📊 Тесты и что они проверяют

### test_01_health_check
**Цель:** Проверка здоровья всех сервисов с авторизацией

**Проверяет:**
- Backend API отвечает
- PostgreSQL подключён
- TimescaleDB подключён
- Redis (опционально)

### test_02_current_user
**Цель:** Проверка данных текущего пользователя

**Проверяет:**
- ID пользователя не пустой
- display_name получен
- email валидный (содержит @)
- Данные реальные, не моки

**Пример вывода:**
```
   User ID: 42
   Display Name: John Doe
   Email: john@example.com
   Created: 2024-01-10T10:00:00

   ✅ User data validated (real, not mocked)
```

### test_03_jira_instances
**Цель:** Проверка подключённых Jira инстансов

**Проверяет:**
- Список сайтов Jira получен
- У каждого сайта есть name и url

**Пример вывода:**
```
   ✅ Found 2 Jira instance(s)
      - Company Jira (https://company.atlassian.net)
      - Dev Jira (https://dev.atlassian.net)
```

### test_04_jira_projects
**Цель:** Получение реальных проектов из Jira

**Проверяет:**
- Проекты получены из реального Jira API
- У проектов есть key, name, id

**Пример вывода:**
```
   ✅ Found 15 project(s)
      - HEALTH: Health Monitoring
      - SCRUM: Scrum Board
      - FASAGM: Fast Agile
      - DEV: Development
      - TEST: Testing
      ... and 10 more
```

### test_05_sync_project
**Цель:** Синхронизация проекта из Jira в БД

**Проверяет:**
- API синхронизации работает
- Задачи создаются/обновляются в БД
- ProjectStatusMapping создаётся

**Пример вывода:**
```
   Syncing project: HEALTH
   Instance: Company Jira

   ✅ Sync completed successfully
   Result: Synced 42 issues
      Created: 42
      Updated: 0
      Total: 42
```

### test_06_dashboard_digest
**Цель:** Проверка дашборда с реальными данными

**Проверяет:**
- `/dashboard/digest` возвращает данные
- Проекты есть в дашборде
- Метрики рассчитаны

**Пример вывода:**
```
   ✅ Dashboard returned data
      Projects: 5
      Team workload entries: 3

   First project in digest:
      Key: HEALTH
      Name: Health Monitoring
      Health: 75.5
```

### test_07_metrics_lead_time
**Цель:** Проверка метрики Lead Time

**Проверяет:**
- Lead Time рассчитывается
- Есть среднее время и количество задач

**Пример вывода:**
```
   ✅ Lead Time calculated
      Average: 48.5 hours
      Total issues: 42
```

### test_08_worker_status
**Цель:** Проверка очереди задач RQ

**Проверяет:**
- Задачи можно поставить в очередь
- Статус задач отслеживается
- Worker обрабатывает задачи

**Пример вывода:**
```
   ✅ Test job queued: abc123-def456
   Job status: finished
```

### test_09_user_metrics
**Цель:** Проверка метрик в БД

**Проверяет:**
- UserMetric записи существуют
- ProjectMetric записи существуют
- ProjectHealth записи существуют

**Пример вывода:**
```
   User metrics records: 10
   Project metrics records: 5
   Project health records: 3

   Latest user metric:
      Workload Index: 0.85
      Activity Score: 75.0
      Tasks completed: 12
```

### test_10_cleanup_options
**Цель:** Опциональная очистка сессии

**Проверяет:**
- Пользователь может выбрать очистку
- Сессия удаляется по выбору

**Пример вывода:**
```
   Do you want to revoke the current session?
   This will log you out.
   Revoke session? [y/N]: y

   ✅ Session revoked (1 session(s) deleted)
```

---

## 🔧 Конфигурация

### Переменные окружения

Создайте `.env.test` в `backend/tests/`:

```bash
# URL API
TEST_BASE_URL=http://localhost:8000

# Таймаут авторизации (секунды)
AUTH_TIMEOUT=300

# Очистка после тестов
E2E_CLEANUP=false  # По умолчанию не очищаем при интерактивном режиме
```

### Маркеры тестов

```python
@pytest.mark.requires_auth  # Требует авторизации
@pytest.mark.e2e  # E2E тест
@pytest.mark.interactive  # Интерактивный ввод
```

---

## 🐛 Диагностика

### Тесты не могут получить сессию

**Проблема:**
```
❌ Timeout: No session created within 300s
```

**Решение:**
1. Убедитесь, что открыли ссылку для авторизации
2. Проверьте, что OAuth flow завершён успешно
3. Проверьте cookies в браузере
4. Увеличьте таймаут: `AUTH_TIMEOUT=600`

### Ошибка 401 Unauthorized

**Проблема:**
```
AssertionError: Dashboard error: {"detail": "Not authenticated"}
```

**Решение:**
1. Проверьте, что сессия активна
2. Выполните `docker-compose exec backend python -c "from app.db.session import SessionLocal; from app.db.models.identity import Session; db=SessionLocal(); print(db.query(Session).filter(Session.expires_at > datetime.utcnow()).count())"`
3. Перезапустите тесты

### Jira API возвращает ошибку

**Проблема:**
```
⚠️  Could not fetch projects: 401
```

**Решение:**
1. Проверьте токены в БД: `SELECT * FROM identity.integration_tokens WHERE provider='jira';`
2. Обновите токен через OAuth
3. Проверьте права доступа к проектам Jira

---

## 📊 Сравнение с моками

### Без авторизации (моки)

```python
# test_e2e_full_cycle.py
def test_02_jira_connection(self):
    # Создаём тестовые данные вручную
    test_project = Project(key="TEST", name="Test Project")
    db_session.add(test_project)
```

### С авторизацией (реальные данные)

```python
# test_e2e_with_auth.py
def test_04_jira_projects(self, jira_projects):
    # Получаем реальные проекты из Jira API
    response = requests.get(
        f"{BASE_URL}/jira/projects",
        headers=auth_headers  # Реальный session_token
    )
    # jira_projects содержит реальные данные
```

---

## ✅ Best Practices

### 1. Используйте существующую сессию

Если сессия уже есть — используйте её:
```
Use this session? [Y/n]: Y
```

### 2. Не очищайте сессию при отладке

Если тестируете один тест — не удаляйте сессию:
```
Revoke session? [y/N]: N
```

### 3. Используйте `-s` флаг

Без `-s` интерактивный ввод не работает:
```bash
pytest tests/test_e2e_with_auth.py -v -s  # ✅
pytest tests/test_e2e_with_auth.py -v     # ❌ (зависнет)
```

### 4. Проверяйте логи

Если тесты падают — проверяйте логи бэкенда:
```bash
docker-compose logs backend --tail=100
```

---

## 📝 Пример полного запуска

```bash
# 1. Запуск всех сервисов
docker-compose up -d

# 2. Проверка здоровья
curl http://localhost:8000/health

# 3. Запуск E2E тестов с авторизацией
docker-compose exec backend pytest tests/test_e2e_with_auth.py -v -s

# Вывод:
# ======================================================================
# 🔐 E2E AUTHENTICATION SETUP
# ======================================================================
# 
# ⚠️  No active session found.
# 
# 📋 AUTHENTICATION REQUIRED
# ----------------------------------------------------------------------
# 
# 1. Open this URL in your browser:
#    http://localhost:8000/auth/login
# 
# 2. Complete OAuth login with Atlassian/GitHub
# 
# 3. Return here and press Enter when ready...
# ----------------------------------------------------------------------
# 
# Press Enter after successful login...
# [Пользователь открывает ссылку, выполняет login, нажимает Enter]
# 
# ⏳ Waiting for session creation...
# ✅ Session created!
#    User: John Doe (john@example.com)
# 
# ======================================================================
# 🔍 STEP 1: Health Check (authenticated)
# ======================================================================
#    ✅ PostgreSQL: connected
#    ✅ TimescaleDB: connected
#    🎉 STEP 1 PASSED
# 
# ... (остальные тесты)
# 
# ======================================================================
# ✅ ALL E2E TESTS COMPLETED
# ======================================================================
```

---

## 📚 Ссылки

- [Основная документация E2E](./E2E_README.md)
- [Pytest Interactive Tests](https://docs.pytest.org/en/latest/how-to/usage.html#specifying-arguments-from-command-line)
- [FastAPI Authentication](https://fastapi.tiangolo.com/tutorial/security/first-steps/)
