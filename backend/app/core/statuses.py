# app/core/statuses.py
# Конфигурация статусов Jira для разных языков

# Статусы, считающиеся "открытыми" (в работе)
OPEN_STATUSES = [
    'In Progress',
    'To Do',
    'Open',
    'Selected for Development',
    'В работе',
    'К выполнению',
    'Backlog'
]

# Статус "закрыто" (выполнено)
CLOSED_STATUS = [
    'Done',
    'Готово',
    'Closed',
    'Выполнено'
]

# Статус "в процессе" (для штрафа за многозадачность)
IN_PROGRESS_STATUSES = [
    'In Progress',
    'В работе',
    'Testing',
    'Testing / QA'
]

def is_open_status(status: str) -> bool:
    """Проверяет, является ли статус открытым"""
    return status in OPEN_STATUSES

def is_closed_status(status: str) -> bool:
    """Проверяет, является ли статус закрытым"""
    return status in CLOSED_STATUS

def is_in_progress_status(status: str) -> bool:
    """Проверяет, является ли статус 'в процессе'"""
    return status in IN_PROGRESS_STATUSES



# Веса для типов задач (если нет Story Points)
ISSUE_TYPE_WEIGHTS = {
    'Bug': 2,
    'Задача': 3,
    'Task': 3,
    'Story': 5,
    'Стори': 5,
    'Epic': 8,
    'Эпик': 8,
    'Sub-task': 1,
    'Подзадача': 1
}

def get_issue_weight(issue_type: str, story_points: float = None) -> float:
    """
    Возвращает вес задачи:
    - если есть Story Points — используем их
    - если нет — конвертируем тип задачи в вес
    - если тип не найден — возвращаем 1 (минимальный вес)
    """
    if story_points is not None and story_points > 0:
        return story_points
    return ISSUE_TYPE_WEIGHTS.get(issue_type, 1)