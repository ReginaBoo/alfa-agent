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

### Авторизация через GitHub OAuth 2.0
- OAuth flow с получением `access_token`
- Получение информации о пользователе (имя, аватар, GitHub ID)
- Получение email пользователя (с поддержкой приватности GitHub)
- Получение списка репозиториев пользователя
- Поддержка Issues API (чтение, создание, обновление)
- Поддержка комментариев к issues
- Поддержка событий (events/timeline) — аналог changelog
- Автообновление токенов (если доступно)
- Привязка GitHub токена к существующему пользователю через сессию

### Хранение данных
- Пользователи (`users`)
- Сессии пользователей (`sessions`)
- Токены для внешних сервисов (`integration_tokens`)
- Сырые события из API (`raw_events`)
- Нормализованные задачи Jira (`jira_issues`)
- Нормализованные страницы Confluence (`confluence_pages`)
- Нормализованные Issues GitHub (`github_issues`)
- История событий GitHub Issues (`github_issue_events`)

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

### GitHub API клиент
- Типизированные Pydantic-модели (`GitHubIssue`, `GitHubRepo`, `GitHubUser`)
- Получение списка репозиториев
- Получение issues из репозитория
- Создание и обновление issues
- Добавление комментариев
- Получение событий (events/timeline) - аналог changelog
- Автообновление токенов при истечении (401 → refresh)
- Поддержка приватных репозиториев

### Синхронизация данных
- Выгрузка задач из Jira в БД (синхронно и асинхронно)
- Выгрузка страниц из Confluence в БД (синхронно и асинхронно)
- Выгрузка issues из GitHub в БД (синхронно и асинхронно)
- Сохранение сырых данных в `raw_events`
- Нормализация и сохранение в соответствующие таблицы

### Фоновые задачи (Очереди Redis + Worker)
- **Четыре очереди:** `sync_jira`, `sync_confluence`, `sync_github`, `calculate_metrics`
- **Worker** в отдельном контейнере для асинхронной обработки
- **Мгновенный ответ API** — задача уходит в очередь, пользователь не ждёт
- **Отслеживание статуса** по `job_id`
- **Надёжность** — задача не теряется при падении воркера

### Метрики и дашборды

#### Workload Index (WI) — индекс загрузки сотрудников
- Суммирование веса задач в открытых статусах
- Расчёт средней скорости закрытия за 2 недели
- Конвертация типа задачи в вес (Bug=2, Task=3, Story=5)
- Штраф за многозадачность (>3 задач → +20%)
- Сохранение в `user_metrics` и `metrics_raw`

#### Activity Score — активность сотрудника
- Оценка от 0 до 100 на основе:
  - Количество закрытых задач (50%)
  - Количество обновлений задач (30%)
  - Количество созданных задач (20%)

#### SLA Score — процент задач, закрытых в срок

#### Project Health Score — общее здоровье проекта (0-100%)

#### Lead Time — среднее время цикла задачи

#### Прогресс задачи — `time_spent / original_estimate * 100%`

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

### GitHub
| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/github/connect` | Получить URL для OAuth авторизации |
| GET | `/github/callback` | Callback после OAuth авторизации |
| GET | `/github/sites` | Список подключённых GitHub инстансов |
| GET | `/github/me` | Информация о текущем пользователе GitHub |
| GET | `/github/repos` | Список репозиториев пользователя |
| GET | `/github/issues` | Issues репозитория (с пагинацией) |
| GET | `/github/issues/{issue_number}` | Конкретный issue |
| POST | `/github/issues` | Создать новый issue |
| PATCH | `/github/issues/{issue_number}` | Обновить issue |
| GET | `/github/issues/{issue_number}/comments` | Комментарии к issue |
| POST | `/github/issues/{issue_number}/comments` | Добавить комментарий |
| GET | `/github/issues/{issue_number}/events` | События (events) для issue |
| GET | `/github/issues/{issue_number}/timeline` | Детальная временная шкала issue |
| POST | `/github/sync/{repo_full_name}` | Синхронизация issues в БД (синхронно) |
| POST | `/github/sync-async/{repo_full_name}` | Синхронизация issues в БД (асинхронно) |
| POST | `/github/sync-all-async` | Синхронизация issues из всех репозиториев (асинхронно) |

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

#### Метрики
| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/metrics/lead-time/{project_key}` | Среднее время цикла задачи |
| GET | `/metrics/progress/{issue_key}` | Прогресс задачи в процентах |
| GET | `/metrics/task-plan/{project_key}` | План по задачам (оценка, затраты, остаток) |
| GET | `/metrics/focus/{project_key}` | Фокусировка команды по типам задач |
| POST | `/metrics/calculate/{project_key}` | Пересчёт метрик (синхронно) |
| POST | `/metrics/calculate-async/{project_key}` | Пересчёт метрик (асинхронно) |
| POST | `/metrics/calculate-all-async` | Пересчёт метрик для всех проектов |


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

## Схема `identity` — пользователи и доступ

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


## Схема `core` — проекты и связи

#### Таблица `projects`
| Поле | Описание |
|------|----------|
| `id` | Уникальный ID проекта |
| `key` | Ключ проекта (SCRUM, FASAGM) |
| `name` | Название проекта |
| `description` | Описание |
| `owner_id` | Владелец проекта |
| `jira_project_key` | Связь с Jira |
| `url` | URL проекта |
| `category` | Категория проекта |
| `is_active` | Активен/архивирован |
| `created_at` | Дата создания |

#### Таблица `user_projects`
| Поле | Описание |
|------|----------|
| `user_id` | ID пользователя |
| `project_id` | ID проекта |
| `role` | Роль (owner, manager, viewer) |

## Схема `raw` — сырые события

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
| `issue_key` | Ключ задачи (PROJ-123) |
| `project_key` | Ключ проекта |
| `summary` | Заголовок |
| `status` | Статус |
| `assignee_account_id` | ID исполнителя |
| `story_points` | Story Points |
| `original_estimate` | Оригинальная оценка (часы) |
| `time_spent` | Затраченное время (часы) |
| `remaining_estimate` | Оставшееся время (часы) |
| `due_date` | Дедлайн |
| `created_at` | Дата создания |
| `updated_at` | Дата обновления |

#### Таблица `issue_changelog`
| Поле | Описание |
|------|----------|
| `id` | Уникальный ID |
| `issue_key` | Ключ задачи |
| `field_name` | Изменённое поле |
| `from_value` | Было |
| `to_value` | Стало |
| `changed_at` | Время изменения |
| `author_account_id` | Кто изменил |

#### Таблица `confluence_pages`
| Поле | Описание |
|------|----------|
| `id` | ID страницы |
| `space_id` | ID пространства |
| `title` | Заголовок страницы |
| `author_id` | ID автора |
| `created_at` | Дата создания |
| `updated_at` | Дата обновления |
| `content` | HTML содержимое |

#### Таблица `github_issues`
| Поле | Описание |
|------|----------|
| `id` | Уникальный ID |
| `issue_id` | GitHub issue ID |
| `issue_number` | Номер issue в репозитории |
| `repo_full_name` | Полное имя репозитория (owner/repo) |
| `title` | Заголовок |
| `body` | Описание |
| `state` | Статус (open, closed) |
| `author_login` | Логин автора |
| `assignee_login` | Логин назначенного |
| `labels` | Метки (через запятую) |
| `comments_count` | Количество комментариев |
| `created_at` | Дата создания |
| `updated_at` | Дата обновления |
| `closed_at` | Дата закрытия |

#### Таблица `github_issue_events`
| Поле | Описание |
|------|----------|
| `id` | Уникальный ID |
| `issue_id` | GitHub issue ID |
| `event_type` | Тип события (assigned, labeled, closed и т.д.) |
| `actor_login` | Логин пользователя, совершившего действие |
| `detail_login` | Деталь события (например, label name) |
| `created_at` | Дата события |

## Схема `public` (TimescaleDB) — метрики

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
| `calculated_at` | Дата расчёта |

#### Таблица `project_metrics`
| Поле | Описание |
|------|----------|
| `id` | Уникальный ID |
| `project_id` | ID проекта |
| `period_start` | Начало периода |
| `period_end` | Конец периода |
| `sla_score` | SLA Score |
| `deadline_stability` | Стабильность дедлайнов |
| `calculated_at` | Дата расчёта |

#### Таблица `project_health`
| Поле | Описание |
|------|----------|
| `id` | Уникальный ID |
| `project_id` | ID проекта |
| `period_start` | Начало периода |
| `period_end` | Конец периода |
| `health_score` | Health Score (0-100) |
| `status` | Статус (green/yellow/red) |

#### Таблица `metrics_raw` (гипертаблица)
| Поле | Описание |
|------|----------|
| `time` | Временная метка |
| `project_id` | ID проекта |
| `user_id` | ID пользователя |
| `metric_name` | Название метрики |
| `value` | Значение |
| `dimensions` | Дополнительные параметры (JSONB) |
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
│ │ ├── github_endpoints.py # /github/* (НОВОЕ!)
│ │ ├── github_auth_endpoints.py # /github/callback (НОВОЕ!)
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
│ ├── github/ # GitHub интеграция (НОВОЕ!)
│ │ ├── oauth.py # OAuth flow
│ │ ├── models.py # Pydantic-модели
│ │ └── client.py # GitHubClient с автопродлением токенов
│ │
│ ├── services/ # Бизнес-логика
│ │ ├── atlassian_service.py # get_user_info, get_working_sites
│ │ ├── token_service.py # TokenService, save_tokens
│ │ ├── token_refresh_service.py # refresh_token, update_user_tokens
│ │ ├── user_service.py # get_or_create_user
│ │ ├── jira_sync_service.py # синхронизация задач Jira в БД
│ │ ├── confluence_sync_service.py # синхронизация страниц Confluence в БД
│ │ ├── github_sync_service.py # синхронизация Issues GitHub в БД (НОВОЕ!)
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


