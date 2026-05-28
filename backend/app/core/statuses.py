# app/core/statuses.py

"""
Fallback-эвристики для статусов Jira.

Основной источник истины:
ProjectStatusMapping в БД.

Этот файл используется только:
- если статусы проекта ещё не синхронизированы
- для heuristic fallback
"""

DEFAULT_CLOSED_KEYWORDS = [
    'done',
    'closed',
    'resolved',
    'completed',
    'finished',
    'готово',
    'выполнено',
    'закрыт',
    'завершен'
]

DEFAULT_IN_PROGRESS_KEYWORDS = [
    'progress',
    'review',
    'testing',
    'development',
    'deploy',
    'работе',
    'тестирование',
    'разработка',
    'проверк',
    'ревью'
]

DEFAULT_OPEN_KEYWORDS = [
    'todo',
    'open',
    'backlog',
    'selected',
    'к выполнению',
    'открыт'
]


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
    - иначе используем вес типа задачи
    """

    if story_points is not None and story_points > 0:
        return story_points

    return ISSUE_TYPE_WEIGHTS.get(issue_type, 1)