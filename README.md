# Alpha Agent Backend

Backend-сервис для интеграции с Atlassian (Jira/Confluence) через OAuth 2.0. Обеспечивает хранение токенов пользователей и доступ к данным проектов.

## Технологии

- **Python 3.11** + **FastAPI** — веб-фреймворк
- **PostgreSQL 15** — база данных
- **SQLAlchemy** — ORM
- **Alembic** — миграции
- **Docker** + **Docker Compose** — контейнеризация
- **OAuth 2.0 (3LO)** — авторизация в Atlassian

---

## Что реализовано

### Авторизация через Atlassian OAuth 2.0
- OAuth flow с получением `access_token` и `refresh_token`
- Автоматическое обновление истекших токенов
- Получение информации о пользователе (email, имя, аватар)

### Хранение данных
- Пользователи (`users`)
- Токены для сайтов Atlassian (`atlassian_tokens`)
- Сессии пользователей (`sessions`)


### Jira API клиент
- Типизированные Pydantic-модели (`JiraIssue`, `JiraProject`, `JiraUser`)
- Поиск задач по JQL через новый эндпоинт `/rest/api/3/search/jql`
- Создание и обновление задач
- Получение истории изменений (changelog)
- Автообновление токенов при истечении


### API endpoints
| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/auth/login` | Начать OAuth авторизацию |
| GET | `/auth/callback` | Callback после авторизации |
| GET | `/jira/sites` | Список доступных сайтов |
| GET | `/jira/projects` | Проекты Jira для указанного сайта |
| GET | `/jira/issues` | Поиск задач по JQL |
| GET | `/jira/issues/{key}` | Получить задачу по ключу |
| POST | `/jira/issues` | Создать новую задачу |
| POST | `/jira/issues/{key}/transitions` | Сменить статус задачи |
| GET | `/jira/issues/{key}/changelog` | История изменений задачи |
| GET | `/health` | Проверка состояния сервиса |


> **Примечание:** Для поиска задач используется новый эндпоинт Atlassian `/rest/api/3/search/jql` (вместо устаревшего `/search`).

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
| `assignee_user_id` | Внешний ключ → external_users |
| `reporter_account_id` | ID автора |
| `priority` | Приоритет |
| `issue_type` | Тип задачи |
| `story_points` | Story Points (оценка сложности) |
| `original_estimate` | Оценка в часах |
| `time_spent` | Затрачено времени |
| `remaining_estimate` | Осталось времени |
| `due_date` | Дедлайн |
| `created_at` | Дата создания |
| `updated_at` | Дата обновления |
| `last_synced_at` | Дата синхронизации |
| `is_deleted` | Флаг удаления |
| `snapshot_version` | Версия снимка |

---



## Архитектура проекта
```
backend/
├── alembic/ # Миграции базы данных
│ ├── versions/ # Сценарии миграций
│ ├── env.py # Настройка Alembic
│ └── script.py.mako # Шаблон миграций
│
├── app/
│ ├── main.py # Точка входа FastAPI
│ │
│ ├── auth/ # Авторизация
│ │ ├── models.py # TokenData, AtlassianResource, UserInfo
│ │ └── oauth.py # OAuth flow
│ │
│ ├── core/ # Основные настройки
│ │ ├── config.py # Переменные окружения
│ │ ├── security.py # Хэширование и безопасность
│ │ └── dependencies.py # get_current_user, get_valid_token
│ │
│ ├── db/ # Работа с БД
│ │ ├── base.py # Базовая модель
│ │ ├── session.py # Сессии БД
│ │ └── models/ # SQLAlchemy модели
│ │ ├── identity.py # users, sessions, integration_tokens
│ │ ├── raw.py # raw_events
│ │ └── normalized.py # jira_issues
│ │
│ ├── endpoints/ # API эндпоинты
│ │ ├── auth_endpoints.py # login, callback
│ │ └── jira_endpoints.py # sites, projects, issues
│ │
│ ├── jira/ # Jira интеграция
│ │ ├── models.py # Pydantic-модели
│ │ └── client.py # JiraClient (типизированный)
│ │
│ ├── services/ # Бизнес-логика
│ │ ├── atlassian_service.py # get_user_info, get_working_sites
│ │ ├── token_service.py # save_tokens_for_working_sites
│ │ ├── token_refresh_service.py # refresh_token, update_user_tokens
│ │ └── user_service.py # get_or_create_user
│ │
│ └── storage/ # Временное хранилище
│ └── memory_store.py
│
├── requirements.txt # Python зависимости
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
```



## Проверка работы
API бэкенда: http://localhost
:8000/docs – Swagger документация

Авторизация: http://localhost:8000/auth/login

