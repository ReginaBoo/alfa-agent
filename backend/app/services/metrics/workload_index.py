"""
Расчёт Workload Index (WI) — индекса загрузки сотрудников.
Формула: WI = (сумма Story Points в открытых статусах) / (средняя velocity за период)
Поддерживает:
- Основной режим: через Story Points
- Альтернативный: через часы (тайм-трекинг)
- Упрощённый: через количество задач
"""

import logging
import math
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Literal
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models import JiraIssue, IntegrationToken
from app.db.models.normalized import ProjectStatusMapping
from app.core.statuses import get_issue_weight
from app.db.timescale import get_timescale_db
from app.services.project_service import get_project_id_by_key
from app.services.metrics.activity_score import calculate_activity_score, save_activity_score

logger = logging.getLogger(__name__)


class WorkloadIndexCalculator:
    """Калькулятор Workload Index с поддержкой разных режимов"""
    
    def __init__(
        self,
        db: Session,
        project_key: str,
        mode: Literal['story_points', 'hours', 'task_count'] = 'story_points',
        focus_factor: float = 0.75,
        work_hours_per_day: float = 8,
        working_days_per_week: float = 5
    ):
        """
        Args:
            db: Сессия PostgreSQL
            project_key: Ключ проекта
            mode: Режим расчёта ('story_points', 'hours', 'task_count')
            focus_factor: Коэффициент фокуса (0.75 = 6 продуктивных часов из 8)
            work_hours_per_day: Рабочих часов в день
            working_days_per_week: Рабочих дней в неделю
        """
        self.db = db
        self.project_key = project_key
        self.mode = mode
        self.focus_factor = focus_factor
        self.work_hours_per_day = work_hours_per_day
        self.working_days_per_week = working_days_per_week
        
        # Получаем динамические статусы из БД
        self._load_project_statuses()
    
    def _load_project_statuses(self):
        """Загружает статусы проекта из БД"""
        mappings = self.db.query(ProjectStatusMapping).filter(
            ProjectStatusMapping.project_key == self.project_key
        ).all()
        
        self.open_statuses = [m.status_name for m in mappings if m.is_open]
        self.in_progress_statuses = [m.status_name for m in mappings if m.is_in_progress]
        self.closed_statuses = [m.status_name for m in mappings if m.is_closed]
        
        # Fallback на случай, если статусы ещё не синхронизированы
        if not self.open_statuses:
            logger.warning(f"No status mappings found for {self.project_key}, using defaults")
            self.open_statuses = ['To Do', 'In Progress', 'Open', 'Backlog', 'К выполнению', 'В работе']
            self.in_progress_statuses = ['In Progress', 'В работе', 'Testing', 'Code Review']
            self.closed_statuses = ['Done', 'Closed', 'Resolved', 'Готово', 'Выполнено']
    
    def _get_adaptive_period(self, assignee_account_id: str = None) -> int:
        """
        Адаптивный период расчёта velocity.
        Возвращает количество недель (2, 4 или 6)
        """
        # Базовый период по умолчанию — 4 недели
        base_weeks = 4
        
        # Запрашиваем историю закрытых задач
        cutoff_date = datetime.utcnow() - timedelta(weeks=6)
        query = self.db.query(JiraIssue).filter(
            JiraIssue.project_key == self.project_key,
            JiraIssue.status.in_(self.closed_statuses),
            JiraIssue.updated_at >= cutoff_date
        )
        
        if assignee_account_id:
            query = query.filter(JiraIssue.assignee_account_id == assignee_account_id)
        
        # Группируем по неделям
        weekly_closed = {}
        for issue in query.all():
            week_num = issue.updated_at.isocalendar()[1]
            week_year = issue.updated_at.isocalendar()[0]
            week_key = f"{week_year}-W{week_num:02d}"
            
            weight = self._get_issue_weight(issue)
            weekly_closed[week_key] = weekly_closed.get(week_key, 0) + weight
        
        weekly_values = list(weekly_closed.values())
        
        if len(weekly_values) < 2:
            return 2  # Мало данных — используем 2 недели
        
        # Проверяем стабильность (коэффициент вариации)
        mean_val = sum(weekly_values) / len(weekly_values)
        if mean_val == 0:
            return 4
        
        variance = sum((v - mean_val) ** 2 for v in weekly_values) / len(weekly_values)
        std_dev = math.sqrt(variance)
        cv = std_dev / mean_val  # Коэффициент вариации
        
        if cv > 0.5:  # Нестабильные данные
            return 6  # Расширяем период
        elif cv < 0.2 and len(weekly_values) >= 4:  # Стабильные, достаточно данных
            return 2  # Можно использовать 2 недели
        else:
            return 4  # Базовый вариант
    
    def _get_issue_weight(self, issue: JiraIssue) -> float:
        """Возвращает вес задачи в зависимости от режима"""
        if self.mode == 'story_points':
            return get_issue_weight(issue.issue_type, issue.story_points)
        elif self.mode == 'hours':
            # Используем remaining_estimate или original_estimate
            if issue.remaining_estimate:
                return issue.remaining_estimate
            elif issue.original_estimate:
                return issue.original_estimate
            else:
                return get_issue_weight(issue.issue_type, None)  # fallback
        else:  # task_count
            return 1.0
    
    def _get_open_weight(self, assignee_account_id: str) -> float:
        """Суммирует вес открытых задач"""
        open_issues = self.db.query(JiraIssue).filter(
            JiraIssue.assignee_account_id == assignee_account_id,
            JiraIssue.project_key == self.project_key,
            JiraIssue.status.in_(self.open_statuses)
        ).all()
        
        total_weight = 0
        for issue in open_issues:
            total_weight += self._get_issue_weight(issue)
        
        logger.info(f"Open weight for {assignee_account_id}: {total_weight} ({self.mode})")
        return total_weight
    
    def _calculate_velocity(
        self,
        assignee_account_id: str,
        weeks: int
    ) -> float:
        """
        Рассчитывает среднюю скорость закрытия за период.
        
        Args:
            assignee_account_id: ID исполнителя
            weeks: Количество недель
        
        Returns:
            float: Средняя скорость в единицах/неделю
        """
        cutoff_date = datetime.utcnow() - timedelta(weeks=weeks)
        
        closed_issues = self.db.query(JiraIssue).filter(
            JiraIssue.assignee_account_id == assignee_account_id,
            JiraIssue.project_key == self.project_key,
            JiraIssue.status.in_(self.closed_statuses),
            JiraIssue.updated_at >= cutoff_date
        ).all()
        
        total_weight = 0
        for issue in closed_issues:
            total_weight += self._get_issue_weight(issue)
        
        if weeks > 0 and total_weight > 0:
            velocity = total_weight / weeks
        else:
            # Минимальная скорость: 1 SP в неделю или 1 задача в неделю
            if self.mode == 'story_points':
                velocity = 1.0
            elif self.mode == 'hours':
                velocity = 8.0  # 8 часов в неделю минимум
            else:
                velocity = 1.0  # 1 задача в неделю
        
        logger.info(f"Velocity for {assignee_account_id} over {weeks} weeks: {velocity} ({self.mode})")
        return velocity
    
    def _calculate_through_hours(
        self,
        assignee_account_id: str,
        period_weeks: int
    ) -> float:
        """
        Альтернативный расчёт WI через часы (тайм-трекинг).
        Формула: WI = (Remaining Estimate) / (рабочие часы * фокус-фактор)
        """
        # Суммируем оставшееся время по открытым задачам
        open_issues = self.db.query(JiraIssue).filter(
            JiraIssue.assignee_account_id == assignee_account_id,
            JiraIssue.project_key == self.project_key,
            JiraIssue.status.in_(self.open_statuses)
        ).all()
        
        remaining_hours = 0
        for issue in open_issues:
            if issue.remaining_estimate:
                remaining_hours += issue.remaining_estimate
            elif issue.original_estimate:
                remaining_hours += issue.original_estimate
            else:
                # Fallback: конвертируем SP в часы (условно 1 SP = 4 часа)
                weight = get_issue_weight(issue.issue_type, issue.story_points)
                remaining_hours += weight * 4
        
        # Доступные рабочие часы за период
        available_hours = period_weeks * self.working_days_per_week * self.work_hours_per_day * self.focus_factor
        
        if available_hours > 0:
            wi = remaining_hours / available_hours
        else:
            wi = remaining_hours
        
        logger.info(f"Hours-based WI for {assignee_account_id}: {wi} (remaining={remaining_hours}h, available={available_hours}h)")
        return wi
    
    def _calculate_by_task_count(
        self,
        assignee_account_id: str,
        weeks: int
    ) -> float:
        """
        Упрощённый расчёт WI через количество задач.
        Формула: WI = (количество открытых задач) / (среднее количество закрытых задач в неделю)
        """
        # Количество открытых задач
        open_count = self.db.query(JiraIssue).filter(
            JiraIssue.assignee_account_id == assignee_account_id,
            JiraIssue.project_key == self.project_key,
            JiraIssue.status.in_(self.open_statuses)
        ).count()
        
        # Среднее количество закрытых задач в неделю
        cutoff_date = datetime.utcnow() - timedelta(weeks=weeks)
        closed_count = self.db.query(JiraIssue).filter(
            JiraIssue.assignee_account_id == assignee_account_id,
            JiraIssue.project_key == self.project_key,
            JiraIssue.status.in_(self.closed_statuses),
            JiraIssue.updated_at >= cutoff_date
        ).count()
        
        avg_closed_per_week = closed_count / weeks if weeks > 0 and closed_count > 0 else 1.0
        
        wi = open_count / avg_closed_per_week if avg_closed_per_week > 0 else open_count
        
        logger.info(f"Task-count WI for {assignee_account_id}: {wi} (open={open_count}, avg_closed/week={avg_closed_per_week})")
        return wi
    
    def calculate_for_user(
        self,
        assignee_account_id: str,
        weeks: int = None,
        adaptive_period: bool = True
    ) -> Optional[float]:
        """
        Рассчитывает Workload Index для конкретного сотрудника.
        
        Args:
            assignee_account_id: ID исполнителя в Jira
            weeks: Количество недель (если None и adaptive_period=True — автовыбор)
            adaptive_period: Использовать адаптивный период
        
        Returns:
            float: Индекс загрузки или None если данных недостаточно
        """
        # Определяем период
        if adaptive_period and weeks is None:
            weeks = self._get_adaptive_period(assignee_account_id)
        elif weeks is None:
            weeks = 4  # По умолчанию 4 недели
        
        # Выбираем режим расчёта
        if self.mode == 'hours':
            wi = self._calculate_through_hours(assignee_account_id, weeks)
        elif self.mode == 'task_count':
            wi = self._calculate_by_task_count(assignee_account_id, weeks)
        else:  # story_points
            open_weight = self._get_open_weight(assignee_account_id)
            velocity = self._calculate_velocity(assignee_account_id, weeks)
            
            if velocity > 0:
                wi = open_weight / velocity
            else:
                wi = open_weight
        
        # Штраф за многозадачность (+20% за каждую задачу сверх 3 в статусе In Progress)
        tasks_in_progress = self.db.query(JiraIssue).filter(
            JiraIssue.assignee_account_id == assignee_account_id,
            JiraIssue.project_key == self.project_key,
            JiraIssue.status.in_(self.in_progress_statuses)
        ).count()
        
        if tasks_in_progress > 3:
            extra_tasks = tasks_in_progress - 3
            penalty = 1 + (extra_tasks * 0.2)  # +20% за каждую лишнюю задачу
            wi = wi * penalty
            logger.info(f"Multitasking penalty: +{(extra_tasks * 20)}% (tasks in progress: {tasks_in_progress})")
        
        return round(wi, 2)
    
    def calculate_for_team(self, weeks: int = None) -> List[Dict[str, Any]]:
        """
        Рассчитывает Workload Index для всех сотрудников проекта.
        
        Returns:
            List[Dict]: Список с результатами для каждого сотрудника
        """
        assignees = self.db.query(JiraIssue.assignee_account_id).filter(
            JiraIssue.project_key == self.project_key,
            JiraIssue.assignee_account_id.isnot(None)
        ).distinct().all()
        
        results = []
        wi_values = []
        
        for (assignee_id,) in assignees:
            wi = self.calculate_for_user(assignee_id, weeks)
            if wi is not None:
                status_info = get_workload_status(wi)
                results.append({
                    'assignee_account_id': assignee_id,
                    'workload_index': wi,
                    'status': status_info['status'],
                    'status_text': status_info['status_text'],
                    'color': status_info['color']
                })
                wi_values.append(wi)
        
        # Сортируем по убыванию WI
        results.sort(key=lambda x: x['workload_index'], reverse=True)
        
        # Рассчитываем Workload Balance
        if wi_values:
            team_wi = sum(wi_values) / len(wi_values)
            balance = calculate_workload_balance(wi_values)
            
            for result in results:
                result['team_wi'] = round(team_wi, 2)
                result['workload_balance'] = balance
        
        return results


def get_workload_status(wi: float) -> dict:
    """
    Возвращает статус загрузки на основе WI.
    Шкала в соответствии с требованиями:
    0.0 – 0.7 — Недогруз
    0.7 – 1.0 — Оптимальная загрузка
    1.0 – 1.3 — Повышенная нагрузка
    > 1.3 — Перегруз
    """
    if wi < 0.7:
        return {'status': 'underloaded', 'status_text': 'Недогруз', 'color': 'orange'}
    elif wi < 1.0:
        return {'status': 'optimal', 'status_text': 'Оптимальная загрузка', 'color': 'green'}
    elif wi <= 1.3:
        return {'status': 'elevated', 'status_text': 'Повышенная нагрузка', 'color': 'yellow'}
    else:
        return {'status': 'overloaded', 'status_text': 'Перегруз', 'color': 'red'}


def calculate_workload_balance(wi_values: List[float]) -> float:
    """
    Рассчитывает Workload Balance — стандартное отклонение WI по команде.
    
    Формула:
    1. Среднее WI команды: mean = sum(WI) / n
    2. Отклонения: (WI - mean)^2
    3. Дисперсия: sum(отклонения) / n
    4. Стандартное отклонение: sqrt(дисперсия)
    
    Интерпретация:
    - < 0.2: нагрузка распределена равномерно
    - 0.2 – 0.5: есть некоторые отклонения
    - > 0.5: критический дисбаланс (есть перегруженные или недогруженные)
    """
    if not wi_values:
        return 0.0
    
    n = len(wi_values)
    mean_wi = sum(wi_values) / n
    
    # Сумма квадратов отклонений
    squared_deviations = sum((wi - mean_wi) ** 2 for wi in wi_values)
    
    # Дисперсия
    variance = squared_deviations / n
    
    # Стандартное отклонение
    std_dev = math.sqrt(variance)
    
    return round(std_dev, 2)


def get_workload_balance_status(balance: float) -> dict:
    """Возвращает статус баланса нагрузки в команде"""
    if balance < 0.2:
        return {'status': 'balanced', 'status_text': 'Нагрузка распределена равномерно', 'color': 'green'}
    elif balance <= 0.5:
        return {'status': 'moderate', 'status_text': 'Есть некоторые отклонения', 'color': 'yellow'}
    else:
        return {'status': 'imbalanced', 'status_text': 'Критический дисбаланс!', 'color': 'red', 'alert': True}


# Совместимость со старым API
def calculate_workload_index(
    db: Session,
    assignee_account_id: str,
    project_key: str,
    weeks: int = 4  # изменено с 2 на 4 недели
) -> Optional[float]:
    """Совместимая функция с новым калькулятором"""
    calculator = WorkloadIndexCalculator(db, project_key, mode='story_points')
    return calculator.calculate_for_user(assignee_account_id, weeks)


def calculate_team_workload(
    db: Session,
    project_key: str,
    weeks: int = 4
) -> List[Dict[str, Any]]:
    """Совместимая функция для расчёта WI команды"""
    calculator = WorkloadIndexCalculator(db, project_key, mode='story_points')
    results = calculator.calculate_for_team(weeks)
    
    # Добавляем баланс нагрузки
    if results:
        wi_values = [r['workload_index'] for r in results]
        balance = calculate_workload_balance(wi_values)
        balance_status = get_workload_balance_status(balance)
        
        for result in results:
            result['workload_balance'] = balance
            result['workload_balance_status'] = balance_status
    
    return results


def get_projects_workload_summary(
    db: Session,
    project_keys: List[str],
    weeks: int = 4,
    mode: Literal['story_points', 'hours', 'task_count'] = 'story_points'
) -> List[Dict[str, Any]]:
    """
    Возвращает сводку по WI для нескольких проектов (для гистограммы Team Workload).
    
    Args:
        db: Сессия PostgreSQL
        project_keys: Список ключей проектов
        weeks: Количество недель для расчёта
        mode: Режим расчёта
    
    Returns:
        List[Dict]: [
            {
                'project_key': 'SCRUM',
                'project_name': 'Scrum Project',
                'team_wi': 0.85,
                'team_wi_percent': 85.0,
                'balance': 0.25,
                'balance_alert': False,  # True если balance > 0.5 (иконка "!")
                'status': 'optimal',
                'status_text': 'Оптимальная загрузка',
                'color': 'green',
                'team_size': 5,
                'members': [...]  # детали по сотрудникам (опционально)
            },
            ...
        ]
    """
    from app.db.models.core import Project
    
    results = []
    
    for project_key in project_keys:
        # Получаем имя проекта из БД
        project = db.query(Project).filter(Project.key == project_key).first()
        project_name = project.name if project else project_key
        
        try:
            calculator = WorkloadIndexCalculator(db, project_key, mode=mode)
            team_results = calculator.calculate_for_team(weeks)
            
            if not team_results:
                # Нет данных по проекту
                results.append({
                    'project_key': project_key,
                    'project_name': project_name,
                    'team_wi': 0,
                    'team_wi_percent': 0,
                    'balance': 0,
                    'balance_alert': False,
                    'status': 'no_data',
                    'status_text': 'Нет данных',
                    'color': 'gray',
                    'team_size': 0,
                    'members': []
                })
                continue
            
            wi_values = [r['workload_index'] for r in team_results]
            team_wi = round(sum(wi_values) / len(wi_values), 2)
            team_wi_percent = round(team_wi * 100, 1)
            
            # Workload Balance (стандартное отклонение)
            balance = calculate_workload_balance(wi_values)
            balance_alert = balance > 0.5  # иконка "!" по требованию
            
            # Статус по шкале WI
            status_info = get_workload_status(team_wi)
            
            # Сортируем членов команды по WI (от самых загруженных)
            members = sorted(team_results, key=lambda x: x['workload_index'], reverse=True)
            
            results.append({
                'project_key': project_key,
                'project_name': project_name,
                'team_wi': team_wi,
                'team_wi_percent': team_wi_percent,
                'balance': balance,
                'balance_alert': balance_alert,
                'status': status_info['status'],
                'status_text': status_info['status_text'],
                'color': status_info['color'],
                'team_size': len(team_results),
                'members': [
                    {
                        'assignee_account_id': m['assignee_account_id'],
                        'workload_index': m['workload_index'],
                        'status': m['status'],
                        'status_text': m['status_text']
                    }
                    for m in members
                ]
            })
            
        except Exception as e:
            logger.error(f"Failed to calculate workload for {project_key}: {e}")
            results.append({
                'project_key': project_key,
                'project_name': project_name,
                'team_wi': 0,
                'team_wi_percent': 0,
                'balance': 0,
                'balance_alert': False,
                'status': 'error',
                'status_text': 'Ошибка расчёта',
                'color': 'gray',
                'team_size': 0,
                'members': [],
                'error': str(e)
            })
    
    # Сортируем по убыванию загрузки
    results.sort(key=lambda x: x['team_wi'], reverse=True)
    
    return results


def get_project_workload_detail(
    db: Session,
    project_key: str,
    weeks: int = 4,
    mode: Literal['story_points', 'hours', 'task_count'] = 'story_points'
) -> Dict[str, Any]:
    """
    Возвращает детальную информацию по загрузке проекта для страницы детального дашборда.
    
    Returns:
        Dict: {
            'project_key': 'SCRUM',
            'project_name': 'Scrum Project',
            'team_wi': 0.85,
            'team_wi_percent': 85.0,
            'balance': 0.25,
            'balance_status': {...},
            'members': [...],
            'distribution': {
                'underloaded': 1,  # количество недогруженных
                'optimal': 3,       # количество с оптимальной загрузкой
                'elevated': 1,      # количество с повышенной нагрузкой
                'overloaded': 0     # количество перегруженных
            }
        }
    """
    calculator = WorkloadIndexCalculator(db, project_key, mode=mode)
    team_results = calculator.calculate_for_team(weeks)
    
    if not team_results:
        return {
            'project_key': project_key,
            'project_name': project_key,
            'team_wi': 0,
            'team_wi_percent': 0,
            'balance': 0,
            'balance_status': get_workload_balance_status(0),
            'members': [],
            'distribution': {
                'underloaded': 0,
                'optimal': 0,
                'elevated': 0,
                'overloaded': 0
            }
        }
    
    wi_values = [r['workload_index'] for r in team_results]
    team_wi = round(sum(wi_values) / len(wi_values), 2)
    team_wi_percent = round(team_wi * 100, 1)
    
    balance = calculate_workload_balance(wi_values)
    balance_status = get_workload_balance_status(balance)
    
    # Распределение по статусам
    distribution = {
        'underloaded': 0,  # WI < 0.7
        'optimal': 0,      # WI 0.7-1.0
        'elevated': 0,     # WI 1.0-1.3
        'overloaded': 0    # WI > 1.3
    }
    
    for r in team_results:
        wi = r['workload_index']
        if wi < 0.7:
            distribution['underloaded'] += 1
        elif wi < 1.0:
            distribution['optimal'] += 1
        elif wi <= 1.3:
            distribution['elevated'] += 1
        else:
            distribution['overloaded'] += 1
    
    # Сортируем членов команды по WI
    members = sorted(team_results, key=lambda x: x['workload_index'], reverse=True)
    
    # Получаем имя проекта
    from app.db.models.core import Project
    project = db.query(Project).filter(Project.key == project_key).first()
    
    return {
        'project_key': project_key,
        'project_name': project.name if project else project_key,
        'team_wi': team_wi,
        'team_wi_percent': team_wi_percent,
        'balance': balance,
        'balance_status': balance_status,
        'members': members,
        'distribution': distribution,
        'weeks': weeks,
        'mode': mode
    }