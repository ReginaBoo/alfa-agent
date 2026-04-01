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

### API endpoints
| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/auth/login` | Начать OAuth авторизацию |
| GET | `/auth/callback` | Callback после авторизации |
| GET | `/jira/sites` | Список доступных сайтов |
| GET | `/jira/projects` | Проекты Jira для указанного сайта |
| GET | `/health` | Проверка состояния сервиса |

---

## Структура базы данных
### Таблица `users` — пользователи
Хранит информацию о пользователях, авторизованных через Atlassian.

| Поле | Описание |
|------|----------|
| `id` | Уникальный ID пользователя |
| `atlassian_account_id` | ID пользователя в Atlassian |
| `email` | Email пользователя |
| `display_name` | Имя пользователя |
| `avatar_url` | Ссылка на аватар |
| `created_at` | Дата регистрации |

---

### Таблица `atlassian_tokens` — токены доступа
Хранит OAuth токены для доступа к Jira/Confluence API.

| Поле | Описание |
|------|----------|
| `id` | Уникальный ID записи |
| `user_id` | Ссылка на пользователя (внешний ключ → users.id) |
| `atlassian_account_id` | ID пользователя в Atlassian (для быстрого поиска) |
| `cloud_id` | ID сайта (рабочего пространства) |
| `site_name` | Имя сайта (например, "mycompany") |
| `site_url` | URL сайта (https://mycompany.atlassian.net) |
| `access_token` | Токен доступа (живет 1 час) |
| `refresh_token` | Токен для обновления (живет 90 дней) |
| `expires_at` | Дата истечения access_token |
| `created_at` | Дата создания записи |

**Особенность:** У одного пользователя может быть несколько записей — по одной на каждый сайт. Однако `access_token` и `refresh_token` одинаковые для всех записей, так как один токен работает для всех сайтов пользователя.

---



## Архитектура проекта
```
backend/
├── alembic/                # Миграции базы данных
│ ├── versions/                 # Сценарии миграций
│ ├── env.py                    # Настройка Alembic
│ └── script.py.mako            # Шаблон миграций
│
├── app/
│ ├── main.py                   # Точка входа FastAPI
│ ├── auth/                     # Работа с авторизацией
│ │ ├── models.py
│ │ ├── oauth.py
│ │ └── service.py
│ │
│ ├── core/                 # Основные настройки проекта
│ │ ├── config.py
│ │ ├── security.py
│ │ └── dependencies.py         # get_current_user, get_valid_token
│ │
│ ├── db/                   # Работа с БД
│ │ ├── base.py
│ │ ├── models.py
│ │ └── session.py
│ │
│ ├── endpoints/            # API эндпоинты
│ │ ├── auth_endpoints.py       # login, callback (использует сервисы)
│ │ └── jira_endpoints.py       # sites, projects (использует dependencies)
│ │
│ ├── services/             # Логика работы
│ │ ├── jira_service.py
│ │ ├── atlassian_service.py      # get_atlassian_user_info, get_working_sites
│ │ ├── user_service.py           # get_or_create_user
│ │ ├── token_service.py          # save_tokens_for_working_sites
│ │ └── token_refresh_service.py  # refresh_token, update_user_tokens
│ │
│ └── storage/              # Временное хранилище токенов
│   └── memory_store.py
│
├── requirements.txt        # Python зависимости
├── Dockerfile              # Docker образ
├── docker-compose.yml      # Компоновка контейнеров
├── .env / .env.example     # Настройки окружения
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

