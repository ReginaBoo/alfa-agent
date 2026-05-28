# backend/scripts/config.py

"""
КОНФИГУРАЦИЯ ДЛЯ ТЕСТОВЫХ СКРИПТОВ JIRA

ИНСТРУКЦИЯ ПО НАСТРОЙКЕ:
========================

1. JIRA_INSTANCE:
   - Замените на ваш Jira instance (например: mycompany.atlassian.net)
   - URL будет: https://your-instance.atlassian.net

2. ADMIN_EMAIL и API_TOKEN:
   - Нужен аккаунт администратора Jira
   - Email: ADMIN_EMAIL = "admin@yourcompany.com"
   - API Token: https://id.atlassian.com/manage-profile/security/api-tokens
   
3. MY_EMAIL:
   - Ваш email (будет руководителем всех проектов)
   - Замените на ваш реальный email в Jira

4. TEST_USERS:
   - Замените на реальных пользователей вашей компании
   - Email должен соответствовать email в Jira

5. TEST_PROJECTS:
   - Замените на реальные проекты вашей компании
   - Ключи проектов должны быть уникальными

6. PROJECT_ASSIGNEES:
   - Замените email на реальных сотрудников вашей команды
"""

# Jira Cloud настройки
JIRA_INSTANCE = "testjiratest-1779538109777"  # Замените на ваш instance (например: newsitealf)
JIRA_URL = f"https://{JIRA_INSTANCE}.atlassian.net"

# Администратор Jira (нужен аккаунт с правами на создание пользователей и проектов)
# Замените на email администратора Jira
ADMIN_EMAIL = "test.jira.test@yandex.ru"

# API Token администратора Jira
# Получить можно здесь: https://id.atlassian.com/manage-profile/security/api-tokens
# Замените на ваш API token
API_TOKEN = "API_TOKEN"

# Ваш email (будет руководителем всех проектов и исполнителем задач)
# Замените на ваш email в Jira
MY_EMAIL = "test.jira.test@yandex.ru"

# ============================================================
# КОНФИГУРАЦИЯ ПРОЕКТОВ (замените на реальные проекты вашей компании)
# ============================================================

TEST_PROJECTS = [
    {
        "key": "HEALTH",
        "name": "Веб-Платформа",
        "description": "Разработка основной веб-платформы",
        "lead": MY_EMAIL,  # Замените на ваш email
        "profile": "healthy",
        "team_size": 5,
        "sla_target": 0.95,
        "workload_target": 0.85
    },
    # ... остальные проекты по аналогии ...
]

# ============================================================
# ОСТАЛЬНАЯ КОНФИГУРАЦИЯ (без изменений)
# ============================================================

# Количество задач по проектам
ISSUES_PER_PROJECT = {
    "HEALTH": 40,
    "CRUNCH": 50,
    "IMBAL": 35,
    "IDLE": 20,
    "BUGS": 45,
    "KANBAN": 38,
    "NEWPROJ": 12
}

# ============================================================
# КОНФИГУРАЦИЯ ПРОЕКТОВ (замените на реальные проекты вашей компании)
# ============================================================

TEST_PROJECTS = [
    {
        "key": "HEALTH",
        "name": "Веб-Платформа",
        "description": "Разработка основной веб-платформы",
        "lead": MY_EMAIL,
        "profile": "healthy",
        "team_size": 5,
        "sla_target": 0.95,
        "workload_target": 0.85
    },
    {
        "key": "CRUNCH",
        "name": "Мобильное Приложение",
        "description": "Разработка мобильного приложения",
        "lead": MY_EMAIL,
        "profile": "overloaded",
        "team_size": 4,
        "sla_target": 0.40,
        "workload_target": 1.45
    },
    {
        "key": "IMBAL",
        "name": "API-Сервис",
        "description": "Разработка API для интеграций",
        "lead": MY_EMAIL,
        "profile": "imbalanced",
        "team_size": 4,
        "sla_target": 0.70,
        "workload_target": 0.90,
        "imbalance_ratio": 0.8
    },
    {
        "key": "IDLE",
        "name": "Документация",
        "description": "Техническая документация",
        "lead": MY_EMAIL,
        "profile": "underloaded",
        "team_size": 3,
        "sla_target": 1.0,
        "workload_target": 0.45
    },
    {
        "key": "BUGS",
        "name": "Поддержка",
        "description": "Техническая поддержка и багфикс",
        "lead": MY_EMAIL,
        "profile": "buggy",
        "team_size": 5,
        "sla_target": 0.55,
        "bug_ratio": 0.6
    },
    {
        "key": "KANBAN",
        "name": "Операционные Задачи",
        "description": "Операционная деятельность",
        "lead": MY_EMAIL,
        "profile": "kanban",
        "team_size": 4,
        "sla_target": 0.85,
        "workflow_stages": 5
    },
    {
        "key": "NEWPROJ",
        "name": "Исследование",
        "description": "R&D проект",
        "lead": MY_EMAIL,
        "profile": "new",
        "team_size": 2,
        "sla_target": None,
        "min_issues": 5
    },
    {
        "key": "FULLCYCLE",
        "name": "Корпоративный Портал",
        "description": "Разработка корпоративного портала с полным циклом",
        "lead": MY_EMAIL,
        "profile": "fullcycle",
        "team_size": 6,
        "sla_target": 0.85,
        "workflow": ["Аналитика", "Код", "Ожидание ревью", "Тестирование", "Бизнес-тестирование", "Внедрение"]
    },
]

# ============================================================
# СОЗДАНИЕ ПОЛЬЗОВАТЕЛЕЙ (20 тестовых пользователей)
# ============================================================

TEST_USERS = [
    # ========== РУКОВОДИТЕЛИ (3 человека) ==========
    {
        "email": "anna.smirnova@test.com",
        "display_name": "Анна Смирнова",
        "role": "team_lead",
        "load_profile": "normal"
    },
    {
        "email": "dmitry.kozlov@test.com",
        "display_name": "Дмитрий Козлов",
        "role": "manager",
        "load_profile": "normal"
    },
    {
        "email": "ivan.krasnov@test.com",
        "display_name": "Иван Краснов",
        "role": "product_owner",
        "load_profile": "normal"
    },
    
    # ========== РАЗРАБОТЧИКИ (10 человек) ==========
    {
        "email": "alexey.ivanov@test.com",
        "display_name": "Алексей Иванов",
        "role": "developer",
        "load_profile": "normal"
    },
    {
        "email": "elena.petrova@test.com",
        "display_name": "Елена Петрова",
        "role": "developer",
        "load_profile": "normal"
    },
    {
        "email": "mikhail.sidorov@test.com",
        "display_name": "Михаил Сидоров",
        "role": "developer",
        "load_profile": "normal"
    },
    {
        "email": "olga.volkova@test.com",
        "display_name": "Ольга Волкова",
        "role": "developer",
        "load_profile": "normal"
    },
    {
        "email": "maxim.vasiliev@test.com",
        "display_name": "Максим Васильев",
        "role": "developer",
        "load_profile": "overloaded"
    },
    {
        "email": "irina.morozova@test.com",
        "display_name": "Ирина Морозова",
        "role": "developer",
        "load_profile": "overloaded"
    },
    {
        "email": "sergey.novikov@test.com",
        "display_name": "Сергей Новиков",
        "role": "developer",
        "load_profile": "underloaded"
    },
    {
        "email": "tatyana.kuzmina@test.com",
        "display_name": "Татьяна Кузьмина",
        "role": "developer",
        "load_profile": "underloaded"
    },
    {
        "email": "andrey.sokolov@test.com",
        "display_name": "Андрей Соколов",
        "role": "developer",
        "load_profile": "normal"
    },
    {
        "email": "ekaterina.belova@test.com",
        "display_name": "Екатерина Белова",
        "role": "developer",
        "load_profile": "normal"
    },
    
    # ========== QA (3 человека) ==========
    {
        "email": "pavel.sokolov@test.com",
        "display_name": "Павел Соколов",
        "role": "qa",
        "load_profile": "normal"
    },
    {
        "email": "natalia.lebedeva@test.com",
        "display_name": "Наталья Лебедева",
        "role": "qa",
        "load_profile": "normal"
    },
    {
        "email": "maria.vinogradova@test.com",
        "display_name": "Мария Виноградова",
        "role": "qa",
        "load_profile": "overloaded"
    },
    
    # ========== АНАЛИТИКИ (2 человека) ==========
    {
        "email": "olga.sokolova@test.com",
        "display_name": "Ольга Соколова",
        "role": "analyst",
        "load_profile": "normal"
    },
    {
        "email": "pavel.volkov@test.com",
        "display_name": "Павел Волков",
        "role": "analyst",
        "load_profile": "normal"
    },
    
    # ========== DEVOPS (1 человек) ==========
    {
        "email": "anton.medvedev@test.com",
        "display_name": "Антон Медведев",
        "role": "devops",
        "load_profile": "normal"
    },
    
    # ========== ДИЗАЙНЕРЫ (1 человек) ==========
    {
        "email": "svetlana.grishina@test.com",
        "display_name": "Светлана Гришина",
        "role": "designer",
        "load_profile": "normal"
    },
]

# ============================================================
# НАЗНАЧЕНИЕ СОТРУДНИКОВ НА ПРОЕКТЫ
# ============================================================

PROJECT_ASSIGNEES = {
    "HEALTH": {
        "team_lead": "anna.smirnova@test.com",
        "product_owner": "ivan.krasnov@test.com",
        "analysts": ["olga.sokolova@test.com", "pavel.volkov@test.com"],
        "developers": ["alexey.ivanov@test.com", "elena.petrova@test.com", "mikhail.sidorov@test.com"],
        "qa": ["pavel.sokolov@test.com", "natalia.lebedeva@test.com"],
        "devops": ["anton.medvedev@test.com"],
        "designers": ["svetlana.grishina@test.com"]
    },
    "CRUNCH": {
        "team_lead": "anna.smirnova@test.com",
        "product_owner": "ivan.krasnov@test.com",
        "analysts": [],
        "developers": ["maxim.vasiliev@test.com", "irina.morozova@test.com", "andrey.sokolov@test.com"],
        "qa": ["maria.vinogradova@test.com"],
        "devops": ["anton.medvedev@test.com"],
        "designers": []
    },
    "IMBAL": {
        "team_lead": "anna.smirnova@test.com",
        "product_owner": "ivan.krasnov@test.com",
        "analysts": ["olga.sokolova@test.com"],
        "developers": ["sergey.novikov@test.com", "tatyana.kuzmina@test.com"],
        "qa": ["natalia.lebedeva@test.com"],
        "devops": [],
        "designers": ["svetlana.grishina@test.com"]
    },
    "IDLE": {
        "team_lead": "anna.smirnova@test.com",
        "product_owner": None,
        "analysts": [],
        "developers": ["sergey.novikov@test.com"],
        "qa": [],
        "devops": [],
        "designers": []
    },
    "BUGS": {
        "team_lead": "anna.smirnova@test.com",
        "product_owner": "ivan.krasnov@test.com",
        "analysts": ["pavel.volkov@test.com"],
        "developers": ["alexey.ivanov@test.com", "elena.petrova@test.com", "mikhail.sidorov@test.com", "ekaterina.belova@test.com"],
        "qa": ["pavel.sokolov@test.com", "natalia.lebedeva@test.com", "maria.vinogradova@test.com"],
        "devops": ["anton.medvedev@test.com"],
        "designers": []
    },
    "KANBAN": {
        "team_lead": "anna.smirnova@test.com",
        "product_owner": None,
        "analysts": ["olga.sokolova@test.com"],
        "developers": ["olga.volkova@test.com", "maxim.vasiliev@test.com", "irina.morozova@test.com", "andrey.sokolov@test.com"],
        "qa": ["pavel.sokolov@test.com"],
        "devops": ["anton.medvedev@test.com"],
        "designers": ["svetlana.grishina@test.com"]
    },
    "NEWPROJ": {
        "team_lead": "anna.smirnova@test.com",
        "product_owner": "ivan.krasnov@test.com",
        "analysts": ["pavel.volkov@test.com"],
        "developers": ["tatyana.kuzmina@test.com", "sergey.novikov@test.com"],
        "qa": [],
        "devops": [],
        "designers": ["svetlana.grishina@test.com"]
    }
}

# ============================================================
# WORKFLOW НАСТРОЙКИ
# ============================================================

PROJECT_WORKFLOWS = {
    "HEALTH": {
        "statuses": ["К выполнению", "В работе", "На проверке", "Готово"],
        "closed_status": "Готово"
    },
    "CRUNCH": {
        "statuses": ["К выполнению", "В работе", "Готово"],
        "closed_status": "Готово"
    },
    "IMBAL": {
        "statuses": ["К выполнению", "В работе", "Тестирование", "Готово"],
        "closed_status": "Готово"
    },
    "KANBAN": {
        "statuses": ["Backlog", "Selected", "In Progress", "Review", "Done"],
        "closed_status": "Done"
    }
}

DEFAULT_WORKFLOW = {
    "statuses": ["To Do", "In Progress", "Done"],
    "closed_status": "Done"
}