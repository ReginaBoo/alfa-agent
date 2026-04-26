# Alpha Agent Backend

Backend-сервис для интеграции с Atlassian (Jira/Confluence) через OAuth 2.0. Обеспечивает хранение токенов пользователей, доступ к данным проектов, расчёт метрик и асинхронную обработку через очереди.

## Технологии

- **Python 3.11** + **FastAPI** — веб-фреймворк
- **PostgreSQL 15** — основная база данных
- **TimescaleDB** — временные ряды для метрик
- **Redis** — очереди задач и кэширование
- **SQLAlchemy** — ORM
- **Alembic** — миграции
- **Docker** + **Docker Compose** — контейнеризация
- **OAuth 2.0 (3LO)** — авторизация в Atlassian
- **RQ (Redis Queue)** — фоновые задачи
- **Pytest** — тестирование

---

## Что реализовано

### Авторизация через Atlassian OAuth 2.0
- OAuth flow с получением `access_token` и `refresh_token`
- Автоматическое обновление истекших токенов
- Получение информации о пользователе (email, имя, аватар)
- Управление сессиями (создание, проверка, удаление)
- Поддержка Jira и Confluence API

### Хранение данных
- Пользователи (`users`)
- Сессии пользователей (`sessions`)
- Токены для внешних сервисов (`integration_tokens`)
- Сырые события из API (`raw_events`)
- Нормализованные задачи Jira (`jira_issues`)
- Нормализованные страницы Confluence (`confluence_pages`)

### Jira API клиент
- Типизированные Pydantic-модели (`JiraIssue`, `JiraProject`, `JiraUser`)
- Поиск задач по JQL
- Создание и обновление задач
- Получение истории изменений (changelog)
- Автообновление токенов при истечении (401 → refresh)
- **Поддержка Story Points** (`customfield_10016`)

### Confluence API клиент
- Получение списка пространств (API v2)
- Получение страниц с пагинацией
- Получение содержимого страниц
- Поиск через CQL
- История версий и комментарии
- Синхронизация страниц в БД

### Синхронизация данных
- Выгрузка задач из Jira в БД (синхронно и асинхронно)
- Выгрузка страниц из Confluence в БД (синхронно и асинхронно)
- Сохранение сырых данных в `raw_events`
- Нормализация и сохранение в соответствующие таблицы

### Фоновые задачи (Очереди Redis + Worker)
- **Три очереди:** `sync_jira`, `sync_confluence`, `calculate_metrics`
- **Worker** в отдельном контейнере для асинхронной обработки
- **Мгновенный ответ API** — задача уходит в очередь, пользователь не ждёт
- **Отслеживание статуса** по `job_id`
- **Надёжность** — задача не теряется при падении воркера

### Метрики и дашборды
- **Workload Index (WI)** — индекс загрузки сотрудников
  - Суммирование Story Points в открытых задачах
  - Расчёт средней скорости закрытия задач
  - Конвертация типа задачи в вес (Bug=2, Task=3, Story=5)
  - Штраф за многозадачность (>3 задач → +20% за каждую)
  - Сохранение в `user_metrics` и `metrics_raw`
- **SLA Score** — процент задач, закрытых в срок
- **Project Health Score** — общее здоровье проекта (0-100%)
- **GET /dashboard/digest** — главная страница дайджеста
- **GET /dashboard/health** — проверка статуса дашборда

### Метрики документации (Confluence)
- **Freshness** — свежесть документации (% страниц, обновлённых за 6 месяцев)
- **Knowledge Distribution** — распределение авторства страниц
- **Coverage** — покрытие задач документацией

### Тестирование
- 20+ тестов, проверяющих:
  - Health check
  - Авторизацию и сессии
  - Зависимости (`get_current_user`, `get_valid_token`)
  - JiraClient и ConfluenceClient (с моками)
  - Jira и Confluence эндпоинты

---

## API endpoints

### Авторизация
| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/auth/login` | Начать OAuth авторизацию (редирект на Atlassian) |
| GET | `/auth/callback` | Callback после авторизации |
| GET | `/auth/me` | Получить информацию о текущем пользователе |
| POST | `/auth/logout` | Выход из системы (удаление сессии) |

### Jira
| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/jira/sites` | Список доступных Atlassian сайтов |
| GET | `/jira/projects` | Проекты Jira для указанного сайта |
| GET | `/jira/issues` | Поиск задач по JQL |
| GET | `/jira/issues/{issue_key}` | Получить задачу по ключу |
| POST | `/jira/issues` | Создать новую задачу |
| POST | `/jira/issues/{issue_key}/transitions` | Сменить статус задачи |
| GET | `/jira/issues/{issue_key}/changelog` | История изменений задачи |
| POST | `/jira/sync/{project_key}` | Синхронизация задач в БД (синхронно) |
| POST | `/jira/sync-async/{project_key}` | Синхронизация задач в БД (асинхронно) |

### Confluence
| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/confluence/spaces` | Список пространств Confluence |
| GET | `/confluence/pages` | Страницы с фильтрацией по пространству |
| GET | `/confluence/pages/{page_id}/content` | Содержимое страницы |
| POST | `/confluence/sync/{space_id}` | Синхронизация страниц в БД (синхронно) |
| POST | `/confluence/sync-async/{space_id}` | Синхронизация страниц в БД (асинхронно) |

### Дашборды
| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/dashboard/digest` | Главная страница с метриками проектов |
| GET | `/dashboard/health` | Проверка статуса дашборда |

### Метрики документации
| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/docs-metrics/freshness` | Свежесть документации |
| GET | `/docs-metrics/knowledge-distribution` | Распределение авторства |
| GET | `/docs-metrics/coverage` | Покрытие задач документацией |

### Очереди (Worker)
| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/worker/test` | Отправить тестовую задачу в очередь |
| GET | `/job/{job_id}` | Проверить статус задачи по job_id |

### Health
| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/health` | Проверка состояния сервиса |

---


## Структура базы данных

### Схема `identity` — пользователи и доступ

#### Таблица `users`
| Поле | Описание |
|------|----------|
| `id` | Уникальный ID пользователя |
| `email` | Email пользователя (уникальный) |
| `display_name` | Отображаемое имя |
| `avatar_url` | Ссылка на аватар |
| `created_at` | Дата регистрации |
| `updated_at` | Дата обновления |

#### Таблица `sessions`
| Поле | Описание |
|------|----------|
| `id` | Уникальный ID сессии |
| `user_id` | Внешний ключ → users.id |
| `session_token` | Уникальный токен сессии |
| `expires_at` | Срок действия |
| `client_type` | Тип клиента (web/desktop) |
| `created_at` | Дата создания |

#### Таблица `integration_tokens`
| Поле | Описание |
|------|----------|
| `id` | Уникальный ID записи |
| `user_id` | Внешний ключ → users.id |
| `provider` | Тип (jira, github, confluence) |
| `provider_user_id` | ID пользователя во внешней системе |
| `instance_id` | ID инстанса (cloud_id для Jira) |
| `instance_name` | Имя сайта (для UI) |
| `instance_url` | URL сайта |
| `access_token` | Токен доступа |
| `refresh_token` | Токен обновления |
| `expires_at` | Срок действия |
| `meta` | Дополнительные данные (JSONB) |
| `created_at` | Дата создания |
| `updated_at` | Дата обновления |

### Схема `raw` — сырые события

#### Таблица `raw_events`
| Поле | Описание |
|------|----------|
| `id` | Уникальный ID |
| `source` | Источник (jira, confluence, github) |
| `event_type` | Тип события |
| `external_id` | ID во внешней системе |
| `project_integration_id` | Связь с проектом |
| `payload` | Полный JSON ответа API |
| `timestamp` | Время события |
| `created_at` | Дата записи |

### Схема `normalized` — нормализованные данные

#### Таблица `jira_issues`
| Поле | Описание |
|------|----------|
| `id` | Уникальный ID |
| `project_integration_id` | Связь с интеграцией |
| `issue_key` | Ключ задачи (PROJ-123) |
| `project_key` | Ключ проекта |
| `summary` | Заголовок |
| `status` | Статус |
| `status_category` | Категория статуса |
| `assignee_account_id` | ID исполнителя |
| `assignee_name` | Имя исполнителя |
| `priority` | Приоритет |
| `issue_type` | Тип задачи |
| `story_points` | Story Points (оценка сложности) |
| `due_date` | Дедлайн |
| `created_at` | Дата создания |
| `updated_at` | Дата обновления |
| `last_synced_at` | Дата синхронизации |

#### Таблица `confluence_pages`
| Поле | Описание |
|------|----------|
| `id` | ID страницы |
| `space_id` | ID пространства |
| `space_key` | Ключ пространства |
| `title` | Заголовок страницы |
| `author_id` | ID автора |
| `version` | Номер версии |
| `status` | Статус |
| `parent_id` | ID родительской страницы |
| `created_at` | Дата создания |
| `updated_at` | Дата обновления |
| `content` | HTML содержимое |
| `last_synced_at` | Дата синхронизации |

### Схема `public` (TimescaleDB) — метрики

#### Таблица `user_metrics`
| Поле | Описание |
|------|----------|
| `id` | Уникальный ID |
| `user_id` | ID пользователя |
| `project_id` | ID проекта |
| `period_start` | Начало периода |
| `period_end` | Конец периода |
| `workload_index` | Индекс загрузки (WI) |
| `activity_score` | Оценка активности |
| `tasks_completed` | Выполненные задачи |
| `commits_count` | Количество коммитов |
| `sla_score` | SLA Score |
| `calculated_at` | Дата расчёта |

#### Таблица `metrics_raw` (гипертаблица)
| Поле | Описание |
|------|----------|
| `time` | Временная метка |
| `project_id` | ID проекта |
| `user_id` | ID пользователя |
| `metric_name` | Название метрики |
| `value` | Значение |
| `dimensions` | Дополнительные параметры (JSONB) |
| `metric_version` | Версия расчёта |
| `is_final` | Флаг финальности |

---



## Архитектура проекта
```
backend/
├── alembic/ # Миграции базы данных
│ └── versions/ # Сценарии миграций
│
├── app/
│ ├── main.py # Точка входа FastAPI
│ │
│ ├── auth/ # Авторизация
│ │ ├── models.py # TokenData, AtlassianResource
│ │ └── oauth.py # OAuth flow
│ │
│ ├── core/ # Основные настройки
│ │ ├── config.py # Переменные окружения
│ │ ├── dependencies.py # get_current_user, get_valid_token
│ │ ├── security.py # Хэширование
│ │ └── statuses.py # Статусы и веса типов задач
│ │
│ ├── db/ # Работа с БД
│ │ ├── base.py # Базовая модель
│ │ ├── session.py # Сессии БД
│ │ ├── timescale.py # Подключение к TimescaleDB
│ │ └── models/ # SQLAlchemy модели
│ │ ├── identity.py # users, sessions, integration_tokens
│ │ ├── raw.py # raw_events
│ │ ├── normalized.py # jira_issues, confluence_pages
│ │ └── metrics.py # user_metrics, project_metrics, metrics_raw
│ │
│ ├── endpoints/ # API эндпоинты
│ │ ├── auth_endpoints.py # /auth/*
│ │ ├── jira_endpoints.py # /jira/*
│ │ ├── confluence_endpoints.py # /confluence/*
│ │ ├── dashboard_endpoints.py # /dashboard/*
│ │ ├── docs_metrics_endpoints.py # /docs-metrics/*
│ │ ├── health.py # /health
│ │ └── worker_test.py # /worker/*
│ │
│ ├── jira/ # Jira интеграция
│ │ ├── models.py # Pydantic-модели
│ │ └── client.py # JiraClient с автопродлением токенов
│ │
│ ├── confluence/ # Confluence интеграция
│ │ ├── models.py # Pydantic-модели
│ │ └── client.py # ConfluenceClient с автопродлением токенов
│ │
│ ├── services/ # Бизнес-логика
│ │ ├── atlassian_service.py # get_user_info, get_working_sites
│ │ ├── token_service.py # TokenService, save_tokens
│ │ ├── token_refresh_service.py # refresh_token, update_user_tokens
│ │ ├── user_service.py # get_or_create_user
│ │ ├── jira_sync_service.py # синхронизация задач Jira в БД
│ │ ├── confluence_sync_service.py # синхронизация страниц Confluence в БД
│ │ └── metrics/ # Метрики
│ │ ├── workload_index.py # расчёт Workload Index
│ │ ├── sla_score.py # расчёт SLA Score
│ │ └── health_score.py # расчёт Project Health Score
│ │
│ └── workers/ # Фоновые задачи
│ ├── queues.py # Настройка очередей Redis
│ └── tasks.py # Задачи для воркеров
│
├── scripts/ # Вспомогательные скрипты
│ └── init_timescale.py # Инициализация TimescaleDB
│
├── tests/ # Тесты
│ ├── conftest.py # Фикстуры для тестов
│ ├── test_health.py # Health check тесты
│ ├── test_auth.py # Тесты авторизации
│ ├── test_dependencies.py # Тесты зависимостей
│ ├── test_jira_client.py # Тесты JiraClient
│ ├── test_jira_endpoints.py # Тесты Jira эндпоинтов
│ └── confluence/ # Тесты Confluence
│ └── test_confluence_client.py
│
├── requirements.txt # Основные зависимости
├── requirements-dev.txt # Зависимости для разработки
├── pytest.ini # Конфигурация pytest
├── Dockerfile # Docker образ
├── docker-compose.yml # Компоновка контейнеров
├── .env / .env.example # Настройки окружения
└── README.md
```

## Быстрый старт

### 1. Клонируем репозиторий и переходим в папку проекта
```
git clone <URL_репозитория>
cd backend
```

### 2. Настройка окружения
```
cp .env.example .env
```
### 3. Запуск
```
# Запуск всех сервисов
docker-compose up -d

# Просмотр логов
docker-compose logs -f backend
```


После сборки приложение будет доступно по адресу: 
http://localhost:8000.

```
 Health check
curl http://localhost:8000/health

# Авторизация через Atlassian
# Откройте в браузере: http://localhost:8000/auth/login

```

## Команды для разработки
```
# Перезапуск после изменений
docker-compose restart backend

# Вход в контейнер
docker-compose exec backend bash

# Применение миграций вручную
docker-compose exec backend alembic upgrade head

# Создание новой миграции
docker-compose exec backend alembic revision --autogenerate -m "description"

# Просмотр логов
docker-compose logs -f backend

# Остановка
docker-compose down

# Запуск тестов
docker-compose exec backend pytest tests/ -v

# Запуск конкретного теста
docker-compose exec backend pytest tests/test_health.py -v
```

## Тестирование

```
# Установка тестовых зависимостей
pip install -r requirements-dev.txt

# Запуск всех тестов
pytest tests/ -v

# Запуск с покрытием
pytest tests/ --cov=app --cov-report=term-missing

# Результат: 19 тестов проходят, 2 с моками требуют доработки
```



## Проверка работы
API бэкенда: http://localhost
:8000/docs – Swagger документация

Авторизация: http://localhost:8000/auth/login


