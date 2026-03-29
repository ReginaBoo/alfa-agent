# Backend Project with FastAPI and Jira Integration

## Описание проекта
FastAPI backend, который позволяет:
- Хранить токены пользователей в базе данных.
- Получать данные о проектах Jira через OAuth2.

Проект написан на **Python 3.11**, использует **SQLAlchemy** для работы с БД и **Alembic** для миграций.

---

## Архитектура проекта
```
backend/
├── alembic/ # Миграции базы данных
│ ├── versions/ # Сценарии миграций
│ ├── env.py # Настройка Alembic
│ └── script.py.mako # Шаблон миграций
├── app/
│ ├── main.py # Точка входа FastAPI
│ ├── auth/ # Работа с авторизацией
│ │ ├── models.py
│ │ ├── oauth.py
│ │ └── service.py
│ ├── core/ # Основные настройки проекта
│ │ ├── config.py
│ │ └── security.py
│ ├── db/ # Работа с БД
│ │ ├── base.py
│ │ ├── models.py
│ │ └── session.py
│ ├── endpoints/ # API эндпоинты
│ │ ├── auth_endpoints.py
│ │ └── jira_endpoints.py
│ ├── services/ # Логика работы с Jira
│ │ └── jira_service.py
│ └── storage/ # Временное хранилище токенов
│ └── memory_store.py
├── requirements.txt # Python зависимости
├── Dockerfile # Docker образ
├── docker-compose.yml # Компоновка контейнеров
├── .env / .env.example # Настройки окружения
└── README.md
```

## Запуск проекта через Docker Compose

### 1. Клонируем репозиторий и переходим в папку проекта
```
git clone <URL_репозитория>
cd backend
```

### 2.Создаём файл окружения
```
cp .env.example .env
```
### 3. Первый запуск (или после изменения зависимостей/Dockerfile)
```
docker-compose up --build
```

Флаг --build пересобирает образ вашего бэкенда.
Команда создаёт контейнеры для бэкенда и PostgreSQL

После сборки приложение будет доступно по адресу: 
http://localhost:8000.
### 4. Обычный запуск без пересборки
```
docker-compose up
```

Поднимает контейнеры из уже собранного образа.
Используется, если код изменился, но Dockerfile и зависимости остались те же.
### 5. Остановка контейнеров
```
docker-compose down
```

Останавливает и удаляет контейнеры, но сохраняет данные в volumes (если они настроены в docker-compose.yml).


## Проверка работы
API бэкенда: http://localhost:8000/docs – Swagger документация

Авторизация: http://localhost:8000/auth/login

Проверка подключения к Jira ((берется пока test_user из бд)): http://localhost:8000/jira/projects 
