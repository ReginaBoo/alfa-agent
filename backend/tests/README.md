# Тесты Alpha Agent Backend

## 📁 Структура

```
tests/
├── conftest.py                 # Общие fixtures
├── e2e_conftest.py             # E2E fixtures
├── test_e2e_full_cycle.py      # E2E тесты (без авторизации, с моками)
├── test_e2e_with_auth.py       # E2E тесты с интерактивной OAuth ⭐ НОВОЕ
├── test_auth.py                # Тесты аутентификации
├── test_health.py              # Тесты health check
├── test_dependencies.py        # Тесты зависимостей
├── test_jira_endpoints.py      # Тесты Jira API
├── test_jira_client.py         # Тесты Jira клиента
├── test_confluence_endpoints.py # Тесты Confluence API
├── confluence/                 # Конфлюэнс тесты
├── jira/                       # Jira тесты
└── fixtures/
    ├── e2e_mocks.py           # Моки для E2E
    └── mock_responses.py       # Тестовые ответы API
```

## 🚀 Запуск тестов

### Все тесты
```bash
docker-compose exec backend pytest tests/ -v
```

### E2E тесты (без авторизации, с моками)
```bash
docker-compose exec backend pytest tests/test_e2e_full_cycle.py -v -s
```

### E2E тесты с интерактивной авторизацией ⭐ НОВОЕ
```bash
docker-compose exec backend pytest tests/test_e2e_with_auth.py -v -s
```

**Важно:** Флаг `-s` обязателен для интерактивного ввода!

### Unit тесты
```bash
docker-compose exec backend pytest tests/ -m "not e2e" -v
```

### С покрытием
```bash
docker-compose exec backend pytest tests/ --cov=app --cov-report=html
```

## 📋 Типы тестов

| Маркер | Описание | Пример |
|--------|----------|--------|
| `unit` | Юнит-тесты (без БД) | `test_calculate_workload()` |
| `integration` | Интеграционные (с API) | `test_jira_sync()` |
| `e2e` | End-to-End (полный цикл) | `test_01_health_check()` |
| `requires_auth` | Требует OAuth авторизации | `test_02_current_user()` |
| `interactive` | Интерактивный ввод пользователя | `test_10_cleanup_options()` |
| `slow` | Медленные тесты | `test_full_dataset()` |

### Разница между E2E тестами

| Характеристика | `test_e2e_full_cycle.py` | `test_e2e_with_auth.py` |
|----------------|--------------------------|-------------------------|
| **Авторизация** | Моки/опционально | **Интерактивная OAuth** |
| **Данные** | Автоматические тестовые | **Реальные из Jira/GitHub** |
| **Сессия** | Не требуется | **Обязательна** |
| **Ввод пользователя** | Нет | **Требует Enter после login** |
| **Очистка** | Автоматическая | **Опциональная** |
| **Запуск** | `pytest ... -v -s` | `pytest ... -v -s` (обязательно!) |
| **Назначение** | Быстрая проверка БД/API | **Тестирование с реальными данными** |

### Пропуск типов тестов

```bash
# Без E2E
pytest tests/ -m "not e2e"

# Без медленных
pytest tests/ --skip-slow

# Только E2E
pytest tests/ -m e2e
```

## 🧪 E2E Тесты

### test_e2e_full_cycle.py — тесты с моками

Подробная документация: [E2E_README.md](./E2E_README.md)

**Шаги теста:**
1. Health check (Backend, PostgreSQL, TimescaleDB, Redis)
2. Jira подключение (API доступность)
3. Синхронизация проектов (в БД)
4. Raw events (сохранение сырых данных)
5. Асинхронная задача (RQ очередь)
6. Workload Index (расчёт метрик)
7. Health Score (композитная метрика)
8. API эндпоинты (дашборд, метрики)
9. Очистка (удаление тестовых данных)
10. Итоговый отчёт

**Запуск:**
```bash
docker-compose exec backend pytest tests/test_e2e_full_cycle.py -v -s
```

---

### test_e2e_with_auth.py — тесты с интерактивной авторизацией ⭐ НОВОЕ

Подробная документация: [E2E_AUTH_README.md](./E2E_AUTH_README.md)

**Шаги теста:**
1. **Health check** с авторизацией
2. **Current user** — проверка данных пользователя из OAuth
3. **Jira instances** — список подключённых инстансов
4. **Jira projects** — реальные проекты из Jira API
5. **Sync project** — синхронизация с реальным проектом
6. **Dashboard digest** — дашборд с реальными данными
7. **Lead Time** — метрика с реальными задачами
8. **Worker status** — очередь задач RQ
9. **User metrics** — метрики в БД
10. **Cleanup options** — опциональная очистка сессии

**Запуск:**
```bash
# ОБЯЗАТЕЛЬНО с флагом -s для интерактивного ввода
docker-compose exec backend pytest tests/test_e2e_with_auth.py -v -s
```

**Процесс авторизации:**
1. Тесты проверяют наличие активной сессии в БД
2. Если нет — выводят ссылку: `http://localhost:8000/auth/login`
3. Ждут нажатия Enter после OAuth login
4. Берут session_token из БД
5. Все API запросы используют этот токен
6. После тестов — опционально отзыв сессии

### Пример вывода

```
============================================================
[14:32:15] STEP 1: Health Check — проверка сервисов
============================================================
   ✅ Backend API: healthy
   ✅ PostgreSQL: connected
   ✅ TimescaleDB: connected
   ⚠️  Redis: not connected (optional)
   🎉 STEP 1 PASSED: All core services are healthy
```

## 🔧 Настройка

### Переменные окружения

Создайте `.env.test` в `backend/tests/`:

```bash
# Jira
TEST_JIRA_INSTANCE=mycompany
TEST_GITHUB_INSTANCE=testuser

# API
TEST_BASE_URL=http://localhost:8000

# Опции тестов
E2E_CLEANUP=true
SKIP_SLOW=false
```

### Тестовые данные

- **Автоматические**: E2E тесты создают минимальные тестовые данные
- **Ручные**: Используйте скрипты в `backend/scripts/`
  - `01_create_test_users.py`
  - `02_create_test_projects.py`
  - `08_create_realistic_test_data.py`

## 📊 Отчётность

### Покрытие кода

```bash
docker-compose exec backend pytest tests/ --cov=app --cov-report=term-missing
```

### XML отчёт (для CI/CD)

```bash
docker-compose exec backend pytest tests/ --junitxml=test-results.xml
```

## 🐛 Диагностика

### Проверка окружения

```bash
# Проверка контейнеров
docker-compose ps

# Проверка БД
docker-compose exec db psql -U postgres -c "SELECT 1"

# Проверка Redis
docker-compose exec redis redis-cli ping

# Логи бэкенда
docker-compose logs backend --tail=100
```

### Частые проблемы

| Проблема | Решение |
|----------|---------|
| `ModuleNotFoundError` | `docker-compose exec backend pip install -r requirements-dev.txt` |
| `Connection refused` | Проверьте, что все сервисы запущены (`docker-compose up -d`) |
| `401 Unauthorized` | Выполните OAuth login через `/auth/login` |
| Тесты зависают | Проверьте очередь RQ (`docker-compose exec backend rq info`) |

## 📚 Ресурсы

- [Pytest Documentation](https://docs.pytest.org/)
- [E2E Тесты](./E2E_README.md)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
