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
JIRA_INSTANCE = "YOUR_INSTANCE"  # Замените на ваш instance (например: newsitealf)
JIRA_URL = f"https://{JIRA_INSTANCE}.atlassian.net"

# Администратор Jira (нужен аккаунт с правами на создание пользователей и проектов)
# Замените на email администратора Jira
ADMIN_EMAIL = "YOUR_ADMIN_EMAIL@company.com"

# API Token администратора Jira
# Получить можно здесь: https://id.atlassian.com/manage-profile/security/api-tokens
# Замените на ваш API token
API_TOKEN = "YOUR_API_TOKEN_HERE"

# Ваш email (будет руководителем всех проектов и исполнителем задач)
# Замените на ваш email в Jira
MY_EMAIL = "YOUR_EMAIL@company.com"

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
]

# ============================================================
# СОЗДАНИЕ ПОЛЬЗОВАТЕЛЕЙ (замените на реальных сотрудников вашей компании)
# ============================================================

TEST_USERS = [
    # ========== ВЫ - ГЛАВНЫЙ РУКОВОДИТЕЛЬ ==========
    {
        "email": MY_EMAIL,
        "display_name": "Ваше Имя",
        "role": "team_lead",
        "load_profile": "normal"
    },
    
    # ========== ОСТАЛЬНЫЕ РУКОВОДИТЕЛИ ==========
    {
        "email": "user1@company.com",
        "display_name": "Имя Фамилия",
        "role": "manager",
        "load_profile": "normal"
    },
    
    # ========== РАЗРАБОТЧИКИ ==========
    {
        "email": "user2@company.com",
        "display_name": "Имя Фамилия",
        "role": "developer",
        "load_profile": "normal"
    },
    {
        "email": "user3@company.com",
        "display_name": "Имя Фамилия",
        "role": "developer",
        "load_profile": "heavy"
    },
    {
        "email": "user4@company.com",
        "display_name": "Имя Фамилия",
        "role": "developer",
        "load_profile": "light"
    },
    
    # ========== QA ==========
    {
        "email": "user5@company.com",
        "display_name": "Имя Фамилия",
        "role": "qa",
        "load_profile": "normal"
    },
    
    # ========== ANALYSTS ==========
    {
        "email": "user6@company.com",
        "display_name": "Имя Фамилия",
        "role": "analyst",
        "load_profile": "normal"
    },
]

# ============================================================
# НАЗНАЧЕНИЕ СОТРУДНИКОВ НА ПРОЕКТЫ (замените на реальных сотрудников)
# ============================================================

PROJECT_ASSIGNEES = {
    "HEALTH": {
        "team_lead": MY_EMAIL,
        "product_owner": "user1@company.com",
        "analysts": ["user6@company.com"],
        "developers": ["user2@company.com", "user3@company.com"],
        "qa": ["user5@company.com"],
        "devops": ["user2@company.com"],
        "designers": ["user4@company.com"]
    },
    "CRUNCH": {
        "team_lead": MY_EMAIL,
        "product_owner": "user1@company.com",
        "analysts": [],
        "developers": ["user3@company.com", "user2@company.com"],
        "qa": ["user5@company.com"],
        "devops": ["user3@company.com"],
        "designers": []
    },
    "IMBAL": {
        "team_lead": MY_EMAIL,
        "product_owner": "user1@company.com",
        "analysts": ["user6@company.com"],
        "developers": ["user4@company.com", "user2@company.com"],
        "qa": ["user5@company.com"],
        "devops": [],
        "designers": ["user4@company.com"]
    },
    "IDLE": {
        "team_lead": MY_EMAIL,
        "product_owner": None,
        "analysts": [],
        "developers": ["user2@company.com"],
        "qa": [],
        "devops": [],
        "designers": []
    },
    "BUGS": {
        "team_lead": MY_EMAIL,
        "product_owner": "user1@company.com",
        "analysts": ["user6@company.com"],
        "developers": ["user3@company.com", "user2@company.com", "user4@company.com"],
        "qa": ["user5@company.com", "user5@company.com"],
        "devops": ["user3@company.com"],
        "designers": []
    },
    "KANBAN": {
        "team_lead": MY_EMAIL,
        "product_owner": None,
        "analysts": ["user6@company.com"],
        "developers": ["user2@company.com", "user4@company.com", "user3@company.com"],
        "qa": ["user5@company.com"],
        "devops": ["user2@company.com"],
        "designers": ["user4@company.com"]
    },
    "NEWPROJ": {
        "team_lead": MY_EMAIL,
        "product_owner": "user1@company.com",
        "analysts": ["user6@company.com"],
        "developers": ["user4@company.com"],
        "qa": [],
        "devops": [],
        "designers": ["user4@company.com"]
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