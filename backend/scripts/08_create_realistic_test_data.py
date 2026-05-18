 #!/мандыusr/bin/env python3
# -*- coding: utf-8 -*-
"""
08_create_realistic_test_data.py

Создаёт РЕАЛИСТИЧНЫЕ тестовые данные для проверки метрик системы.

Что делает:
- Создаёт задачи с РАЗНЫМИ датами (распределёнными по неделям/месяцам)
- Задачи в РАЗНЫХ статусах (не только Created/Done)
- Разные временные интервалы между переходами (от 1 до 30 дней)
- Разные сценарии для каждого профиля проекта
- Реалистичные описания задач для обучения модели

Запуск: python scripts/08_create_realistic_test_data.py
"""

import requests
import sys
import time
import json
import random
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import (
    JIRA_URL, ADMIN_EMAIL, API_TOKEN,
    PROJECT_ASSIGNEES, ISSUES_PER_PROJECT,
    PROJECT_WORKFLOWS, DEFAULT_WORKFLOW
)


def print_info(msg: str): print(f"INFO: {msg}")
def print_success(msg: str): print(f"OK: {msg}")
def print_error(msg: str): print(f"ERR: {msg}")
def print_warn(msg: str): print(f"WARN: {msg}")


# Реалистичные описания задач для разных типов
TASK_DESCRIPTIONS = {
    "Task": [
        "Необходимо реализовать функционал экспорта данных в формате CSV с возможностью фильтрации по датам и категориям. Требуется протестировать на больших объемах данных (более 100k записей).",
        "Доработать интерфейс административной панели: добавить возможность массового редактирования статусов, улучшить валидацию полей, добавить подтверждение действий.",
        "Оптимизировать запросы к базе данных для ускорения формирования отчетов. Профилировать текущую реализацию, выявить узкие места, внедрить кэширование.",
        "Интегрировать внешний API платежной системы. Реализовать обработку webhook уведомлений, реализовать механизм повторных попыток при ошибках.",
        "Обновить документацию REST API: добавить примеры запросов/ответов, описать все возможные ошибки, добавить примеры на разных языках программирования.",
        "Настроить мониторинг производительности микросервисов. Внедрить сбор метрик, настроить алерты при превышении пороговых значений.",
        "Реализовать функционал импорта данных из Excel файлов. Поддержать несколько форматов файлов, добавить предпросмотр данных перед импортом.",
        "Доработать систему уведомлений: добавить email рассылку, реализовать настройки частоты уведомлений, добавить шаблонизацию писем.",
    ],
    "Bug": [
        "При попытке экспорта больших объемов данных возникает ошибка таймаута. Ошибка воспроизводится на данных более 50k записей. Требуется добавить пагинацию или асинхронную обработку.",
        "Некорректно отображаются даты в отчете при смене часового пояса. Проблема воспроизводится для пользователей в часовых поясах UTC+3 и далее.",
        "Валидация формы регистрации пропускает недопустимые email адреса с спецсимволами. Требуется усилить валидацию на фронтенде и бэкенде.",
        "При одновременном редактировании одной записи двумя пользователями происходит потеря данных. Требуется внедрить оптимистичную блокировку.",
        "Кэш не обновляется после изменения конфигурации. Требуется добавить механизм инвалидации кэша при изменениях настроек.",
        "Мобильная версия сайта некорректно отображается на устройствах с разрешением 320px. Проблема с адаптивной версткой в блоке футера.",
        "Платежи в валюте USD не проходят из-за неправильного форматирования десятичных знаков. Ошибка в валидаторе сумм платежей.",
    ],
    "Story": [
        "Как пользователь, я хочу иметь возможность сохранять черновики форм, чтобы иметь возможность вернуться к заполнению позже. Требуется реализовать автосохранение каждые 5 минут и ручное сохранение черновика.",
        "Как администратор, я хочу видеть детальную статистику активности пользователей за период, чтобы анализировать вовлеченность. Нужны графики, экспорт в CSV, фильтры по датам и ролям.",
        "Как менеджер проекта, я хочу назначать задачи нескольким исполнителям, чтобы распределять работу внутри команды. Требуется изменить UI создания задачи и логику уведомлений.",
        "Как разработчик, я хочу иметь возможность быстро развернуть тестовое окружение через Docker Compose, чтобы ускорить процесс разработки и тестирования.",
        "Как пользователь, я хочу получать уведомления о изменениях статуса задачи в реальном времени через WebSocket, чтобы быть в курсе обновлений без необходимости обновлять страницу.",
        "Как владелец продукта, я хочу видеть дорожную карту разработки с оценкой сроков, чтобы планировать релизы и communicating со стейкхолдерами.",
    ]
}


def create_issue_with_assignee(
    project_key: str,
    issue_type: str,
    summary: str,
    description: str,
    assignee_id: str,
    story_points: Optional[float] = None,
    priority: str = "Medium",
    labels: List[str] = None
) -> Optional[str]:
    """Создаёт задачу с назначением исполнителя"""
    
    auth = (ADMIN_EMAIL, API_TOKEN)
    url = f"{JIRA_URL}/rest/api/3/issue"
    
    payload = {
        "fields": {
            "project": {"key": project_key},
            "summary": summary,
            "issuetype": {"name": issue_type},
            "priority": {"name": priority},
            "assignee": {"accountId": assignee_id},
            "description": {
                "type": "doc",
                "version": 1,
                "content": [{
                    "type": "paragraph",
                    "content": [{"type": "text", "text": description}]
                }]
            }
        }
    }
    
    if story_points is not None:
        payload["fields"]["customfield_10016"] = story_points
    
    if labels:
        payload["fields"]["labels"] = labels
    
    try:
        resp = requests.post(url, json=payload, auth=auth, 
                           headers={"Content-Type": "application/json"}, timeout=60)
        
        if resp.status_code == 201:
            return resp.json().get('key')
        else:
            try:
                error_data = resp.json()
                errors = error_data.get('errorMessages', [])
                if not errors:
                    errors = list(error_data.get('errors', {}).values()) or ['Unknown error']
                print_error(f"Не удалось создать задачу: {errors[0]}")
            except:
                print_error(f"Ошибка создания: статус {resp.status_code}")
            return None
    except Exception as e:
        print_error(f"Исключение при создании: {e}")
        return None


def get_transitions(issue_key: str) -> List[Dict]:
    """Получает доступные переходы"""
    auth = (ADMIN_EMAIL, API_TOKEN)
    url = f"{JIRA_URL}/rest/api/3/issue/{issue_key}/transitions"
    
    try:
        resp = requests.get(url, auth=auth, timeout=60)
        if resp.status_code == 200:
            return resp.json().get('transitions', [])
        return []
    except Exception:
        return []


def get_current_status(issue_key: str) -> Optional[str]:
    """Получает текущий статус"""
    auth = (ADMIN_EMAIL, API_TOKEN)
    url = f"{JIRA_URL}/rest/api/3/issue/{issue_key}?fields=status"
    
    try:
        resp = requests.get(url, auth=auth, timeout=60)
        if resp.status_code == 200:
            return resp.json().get('fields', {}).get('status', {}).get('name')
        return None
    except Exception:
        return None


def transition_issue(issue_key: str, transition_id: str, comment: str) -> bool:
    """Выполняет переход с комментарием"""
    
    auth = (ADMIN_EMAIL, API_TOKEN)
    url = f"{JIRA_URL}/rest/api/3/issue/{issue_key}/transitions"
    
    payload = {
        "transition": {"id": transition_id},
        "update": {
            "comment": [{
                "add": {
                    "body": {
                        "type": "doc",
                        "version": 1,
                        "content": [{
                            "type": "paragraph",
                            "content": [{"type": "text", "text": comment}]
                        }]
                    }
                }
            }]
        }
    }
    
    try:
        resp = requests.post(url, json=payload, auth=auth, timeout=60)
        return resp.status_code == 204
    except Exception as e:
        print_warn(f"   Переход не удал: {e}")
        return False


def set_issue_created_date(issue_key: str, created_date: datetime) -> bool:
    """Устанавливает дату создания задачи"""
    auth = (ADMIN_EMAIL, API_TOKEN)
    url = f"{JIRA_URL}/rest/api/3/issue/{issue_key}"
    
    payload = {
        "update": {
            "historyMetadata": {
                "authorName": "Test Data Generator"
            }
        },
        "fields": {
            "created": created_date.strftime("%Y-%m-%dT%H:%M:%S")
        }
    }
    
    try:
        resp = requests.put(url, json=payload, auth=auth, timeout=60)
        return resp.status_code == 204
    except Exception:
        return False


def get_realistic_description(issue_type: str) -> str:
    """Получает реалистичное описание для типа задачи"""
    descriptions = TASK_DESCRIPTIONS.get(issue_type, TASK_DESCRIPTIONS["Task"])
    return random.choice(descriptions)


def create_issue_with_scenario(
    project_key: str,
    workflow: Dict,
    scenario: str,
    issue_num: int,
    your_account_id: str
) -> Optional[Dict]:
    """
    Создаёт задачу с реалистичным сценарием и назначением тебе
    """
    
    statuses = workflow.get('statuses', DEFAULT_WORKFLOW['statuses'])
    closed_status = workflow.get('closed_status', DEFAULT_WORKFLOW['closed_status'])
    
    # Выбираем тип задачи по сценарию
    if 'bug' in scenario:
        issue_type = "Bug"
        story_points = random.choice([1, 2, 3])
        priority = random.choice(["High", "Highest", "Medium"])
    elif 'story' in scenario:
        issue_type = "Story"
        story_points = random.choice([5, 8, 13])
        priority = random.choice(["High", "Medium"])
    else:
        issue_type = random.choice(["Task", "Task", "Story"])
        story_points = random.choice([2, 3, 5, 8])
        priority = random.choice(["Low", "Medium", "High"])
    
    # Даты
    today = datetime.now()
    if scenario in ["open_new"]:
        created_date = today - timedelta(days=random.randint(1, 5))
    elif scenario in ["open_progress"]:
        created_date = today - timedelta(days=random.randint(7, 20))
    elif scenario in ["stuck_progress", "stuck_review"]:
        created_date = today - timedelta(days=random.randint(15, 40))
    elif scenario in ["closed_fast"]:
        created_date = today - timedelta(days=random.randint(14, 30))
    else:  # closed_normal, closed_slow
        created_date = today - timedelta(days=random.randint(30, 120))
    
    # Описание
    description = get_realistic_description(issue_type)
    
    # Summary
    type_prefix = {"Task": "[TASK]", "Bug": "[BUG]", "Story": "[STORY]"}
    prefix = type_prefix.get(issue_type, "[TASK]")
    summary = f"{prefix} {project_key}-{issue_num}: {scenario.replace('_', ' ').title()}"
    
    # Метки
    labels = ["test-data", scenario.replace("_", "-")]
    
    print_info(f"Создание {summary}...")
    
    # Создаём задачу с назначением тебе
    issue_key = create_issue_with_assignee(
        project_key=project_key,
        issue_type=issue_type,
        summary=summary,
        description=description,
        assignee_id=your_account_id,
        story_points=story_points,
        priority=priority,
        labels=labels
    )
    
    if not issue_key:
        return None
    
    print(f"   Создана {issue_key}")
    
    if scenario in ["open_new"]:
        # Новая задача - не трогаем
        return {
            "key": issue_key,
            "type": issue_type,
            "closed": False,
            "scenario": scenario,
            "created_date": created_date.strftime('%Y-%m-%d')
        }
        
    # Получаем переходы
    time.sleep(0.5)
    transitions = get_transitions(issue_key)
    
    if not transitions:
        print_warn("   Нет доступных переходов")
        return {
            "key": issue_key,
            "type": issue_type,
            "closed": False,
            "scenario": scenario,
            "created_date": created_date.strftime('%Y-%m-%d'),
            "error": "no_transitions"
        }
    
    transition_map = {t.get('to', {}).get('name'): t for t in transitions}
    
    # Выполняем переходы в зависимости от сценария
    transitions_log = []
    
    if scenario == "closed_fast":
        # Полный цикл быстро
        target_statuses = statuses[1:]
        days_per_status = random.randint(1, 3)
        
    elif scenario == "closed_normal":
        # Полный цикл нормально
        target_statuses = statuses[1:]
        days_per_status = random.randint(3, 7)
        
    elif scenario == "closed_slow":
        # Полный цикл медленно
        target_statuses = statuses[1:]
        days_per_status = random.randint(7, 15)
        
    elif scenario == "stuck_progress":
        # Застряла в работе
        target_statuses = [statuses[1]] if len(statuses) > 1 else []
        days_per_status = random.randint(10, 20)
        
    elif scenario == "stuck_review":
        # Застряла на проверке
        review_statuses = ["На проверке", "Review", "Тестирование"]
        review_idx = None
        for i, s in enumerate(statuses):
            if s in review_statuses:
                review_idx = i
                break
        target_statuses = statuses[1:review_idx+1] if review_idx else statuses[1:2]
        days_per_status = random.randint(5, 10)
        
    elif scenario == "open_progress":
        # В работе
        target_statuses = [statuses[1]] if len(statuses) > 1 else []
        days_per_status = random.randint(5, 15)
        
    else:
        target_statuses = statuses[1:]
        days_per_status = 5
    
    current_date = created_date
    transitions_made = 0
    
    for i, target in enumerate(target_statuses):
        if target not in transition_map:
            print_warn(f"   Нет перехода в {target}")
            continue
        
        current_date += timedelta(days=days_per_status)
        
        # Комментарий
        if i == 0:
            comment = "Задача взята в работу"
        elif target in ["На проверке", "Review", "Тестирование"]:
            comment = "Передано на проверку"
        elif target == closed_status:
            comment = "Задача завершена и проверена"
        else:
            comment = "Продолжается работа над задачей"
        
        success = transition_issue(issue_key, transition_map[target]['id'], comment)
        
        if success:
            transitions_made += 1
            print(f"   -> {target} ({days_per_status} дн.)")
            transitions_log.append({
                "to": target,
                "date": current_date.strftime('%Y-%m-%d'),
                "comment": comment
            })
            
            if target == closed_status:
                print(f"   ЗАКРЫТА")
                break
        
        time.sleep(0.3)
    
    final_status = get_current_status(issue_key)
    is_closed = final_status == closed_status
    
    return {
        "key": issue_key,
        "type": issue_type,
        "story_points": story_points,
        "closed": is_closed,
        "transitions": transitions_made,
        "final_status": final_status,
        "scenario": scenario,
        "created_date": created_date.strftime('%Y-%m-%d'),
        "transitions_log": transitions_log
    }


def get_scenarios_for_project(profile: str, total: int) -> List[str]:
    """Определяет сценарии для проекта на основе профиля"""
    
    scenarios = []
    
    if profile == "healthy":
        scenarios.extend(["closed_fast"] * 5)
        scenarios.extend(["closed_normal"] * 12)
        scenarios.extend(["closed_slow"] * 3)
        scenarios.extend(["stuck_progress"] * 3)
        scenarios.extend(["stuck_review"] * 2)
        scenarios.extend(["open_new"] * 5)
        scenarios.extend(["open_progress"] * 5)
        
    elif profile == "overloaded":
        scenarios.extend(["closed_fast"] * 10)
        scenarios.extend(["closed_normal"] * 10)
        scenarios.extend(["bug"] * 15)
        scenarios.extend(["stuck_progress"] * 5)
        scenarios.extend(["open_progress"] * 5)
        scenarios.extend(["open_new"] * 5)
        
    elif profile == "imbalanced":
        scenarios.extend(["closed_normal"] * 10)
        scenarios.extend(["stuck_progress"] * 5)
        scenarios.extend(["stuck_review"] * 5)
        scenarios.extend(["open_progress"] * 8)
        scenarios.extend(["open_new"] * 4)
        scenarios.extend(["bug"] * 3)
        
    elif profile == "underloaded":
        scenarios.extend(["closed_slow"] * 5)
        scenarios.extend(["stuck_progress"] * 5)
        scenarios.extend(["stuck_review"] * 5)
        scenarios.extend(["open_progress"] * 3)
        scenarios.extend(["open_new"] * 2)
        
    elif profile == "buggy":
        scenarios.extend(["bug"] * 25)
        scenarios.extend(["closed_fast"] * 8)
        scenarios.extend(["closed_normal"] * 5)
        scenarios.extend(["open_new"] * 4)
        scenarios.extend(["open_progress"] * 3)
        
    elif profile == "kanban":
        scenarios.extend(["closed_fast"] * 10)
        scenarios.extend(["closed_normal"] * 10)
        scenarios.extend(["open_new"] * 6)
        scenarios.extend(["open_progress"] * 6)
        scenarios.extend(["stuck_progress"] * 2)
        
    else:
        scenarios.extend(["closed_normal"] * 8)
        scenarios.extend(["closed_fast"] * 5)
        scenarios.extend(["stuck_progress"] * 3)
        scenarios.extend(["open_new"] * 4)
        scenarios.extend(["open_progress"] * 4)
    
    if len(scenarios) < total:
        while len(scenarios) < total:
            scenarios.append(random.choice(["open_new", "open_progress", "closed_normal"]))
    else:
        scenarios = scenarios[:total]
    
    random.shuffle(scenarios)
    return scenarios


def main():
    print("=" * 70)
    print("СОЗДАНИЕ РЕАЛИСТИЧНЫХ ТЕСТОВЫХ ДАННЫХ")
    print("=" * 70)
    
    # Загружаем пользователей
    users_file = os.path.join(os.path.dirname(__file__), '.test_users.json')
    if not os.path.exists(users_file):
        print_error("Файл с пользователями не найден!")
        print("Сначала запустите: python scripts/01_create_test_users.py")
        return
    
    with open(users_file, 'r', encoding='utf-8') as f:
        users = json.load(f)
    users_by_email = {user['email']: user['account_id'] for user in users}
    print_info(f"Пользователей: {len(users_by_email)}")
    
    # Получаем ваш accountId
    your_account_id = users_by_email.get(MY_EMAIL)
    if not your_account_id:
        print_error(f"Ваш аккаунт ({MY_EMAIL}) не найден в созданных пользователях!")
        print("Убедитесь, что вы добавили свой email в TEST_USERS в config.py")
        return
    print_info(f"Ваш accountId: {your_account_id}")
    
    # Проверка подключения
    print_info("Проверка подключения...")
    try:
        resp = requests.get(f"{JIRA_URL}/rest/api/3/serverInfo", 
                           auth=(ADMIN_EMAIL, API_TOKEN), timeout=30)
        if resp.status_code != 200:
            print_error("Ошибка подключения к Jira")
            return
        print_success("Подключено к Jira")
    except Exception as e:
        print_error(f"Ошибка: {e}")
        return
    
    # Проекты с профилями
    projects_config = {
        "HEALTH": {"profile": "healthy", "workflow": PROJECT_WORKFLOWS.get("HEALTH", DEFAULT_WORKFLOW)},
        "CRUNCH": {"profile": "overloaded", "workflow": PROJECT_WORKFLOWS.get("CRUNCH", DEFAULT_WORKFLOW)},
        "IMBAL": {"profile": "imbalanced", "workflow": PROJECT_WORKFLOWS.get("IMBAL", DEFAULT_WORKFLOW)},
        "IDLE": {"profile": "underloaded", "workflow": PROJECT_WORKFLOWS.get("IDLE", DEFAULT_WORKFLOW)},
        "BUGS": {"profile": "buggy", "workflow": PROJECT_WORKFLOWS.get("BUGS", DEFAULT_WORKFLOW)},
        "KANBAN": {"profile": "kanban", "workflow": PROJECT_WORKFLOWS.get("KANBAN", DEFAULT_WORKFLOW)},
    }
    
    all_results = {}
    total_created = 0
    total_closed = 0
    total_stuck = 0
    total_open = 0
    
    for project_key, config in projects_config.items():
        profile = config['profile']
        workflow = config['workflow']
        total_issues = ISSUES_PER_PROJECT.get(project_key, 20)
        statuses = workflow.get('statuses', DEFAULT_WORKFLOW['statuses'])
        
        print(f"\n{'='*70}")
        print(f"Проект: {project_key} (профиль: {profile})")
        print(f"{'='*70}")
        print(f"   Workflow: {' -> '.join(statuses)}")
        print(f"   Задач: {total_issues}")
        
        scenarios = get_scenarios_for_project(profile, total_issues)
        
        project_results = []
        
        for i, scenario in enumerate(scenarios, 1):
            result = create_issue_with_scenario(
                project_key=project_key,
                workflow=workflow,
                scenario=scenario,
                issue_num=i,
                your_account_id=your_account_id
            )
            
            if result:
                project_results.append(result)
                total_created += 1
                
                if result.get('closed'):
                    total_closed += 1
                elif result.get('scenario') in ['stuck_progress', 'stuck_review']:
                    total_stuck += 1
                else:
                    total_open += 1
            
            time.sleep(0.8)
        
        all_results[project_key] = project_results
        
        closed_in_project = sum(1 for r in project_results if r.get('closed'))
        print(f"\nOK Проект {project_key}: {len(project_results)} задач, закрыто {closed_in_project}")
    
    # Итоговый отчёт
    print(f"\n{'='*70}")
    print("ИТОГОВЫЙ ОТЧЁТ")
    print(f"{'='*70}")
    print(f"   Всего создано задач: {total_created}")
    print(f"   Закрыто: {total_closed} ({total_closed/total_created*100:.1f}%)")
    print(f"   Застрявшие: {total_stuck}")
    print(f"   Открытые: {total_open}")
    
    # Сохранение
    result_file = 'scripts/.realistic_test_data.json'
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump({
            "results": all_results,
            "summary": {
                "total_created": total_created,
                "total_closed": total_closed,
                "total_stuck": total_stuck,
                "total_open": total_open
            },
            "created_at": datetime.now().isoformat()
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\nРезультаты сохранены в {result_file}")
    
    print(f"\n{'='*70}")
    print("СЛЕДУЮЩИЙ ШАГ:")
    print("   python scripts/04_sync_and_check.py")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
