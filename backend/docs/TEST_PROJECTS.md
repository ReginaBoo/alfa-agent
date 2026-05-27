# Jira Test Projects

Цель:

Создать набор детерминированных Jira-проектов для:

- тестирования ingestion
- тестирования normalize layer
- тестирования changelog
- тестирования transitions
- тестирования метрик
- тестирования Story Points
- тестирования assignee analytics
- тестирования velocity
- тестирования WIP
- тестирования lead time
- тестирования cycle time

---

# ОБЩИЕ ПРАВИЛА

Все проекты создаются через Jira REST API.

Все transitions делаются ТОЛЬКО через:

POST /rest/api/3/issue/{issueKey}/transitions

Запрещено менять status через issue update.

Причина:

иначе Jira НЕ создаст changelog transitions.

Это ломает:

- lead time
- cycle time
- status history
- workflow analytics

---

# ОБЩИЕ НАСТРОЙКИ

## Statuses

Используемые статусы:

- Backlog
- To Do
- In Progress
- Testing / QA
- Done

## Issue Types

Используемые issue types:

- Epic
- Task
- Bug
- Subtask

## Story Points

Используется поле:

Story point estimate

API field:

customfield_10016

Пример:

```json
{
  "fields": {
    "customfield_10016": 5
  }
}
```

---

# PROJECT 1 — IDEAL

Цель:

Проверка корректного happy-path сценария.

Ожидаем:

- высокая completion rate
- корректный velocity
- корректный lead time
- низкий WIP
- корректный changelog

---

## Сценарии задач

### TASK-1

Тип:

Task

Story Points:

3

Workflow:

Backlog
→ To Do
→ In Progress
→ Testing / QA
→ Done

Assignee:

alena

---

### TASK-2

Тип:

Task

Story Points:

5

Workflow:

Backlog
→ To Do
→ In Progress
→ Done

Assignee:

alena

---

### BUG-1

Тип:

Bug

Story Points:

2

Workflow:

To Do
→ In Progress
→ Done

Assignee:

alena

---

## Ожидаемые метрики

Velocity:

3 + 5 + 2 = 10

Done issues:

3

WIP:

0

Completion rate:

100%

---

# PROJECT 2 — CHAOS

Цель:

Проверка деградации метрик.

Ожидаем:

- высокий WIP
- низкий completion rate
- перегрузка
- много задач в работе
- broken workflow behavior

---

## Сценарии задач

### TASK-1

Task

SP: 8

Workflow:

Backlog
→ In Progress

Текущий статус:

In Progress

---

### TASK-2

Task

SP: 5

Workflow:

Backlog
→ In Progress
→ Testing / QA

Текущий статус:

Testing / QA

---

### TASK-3

Task

SP: 13

Workflow:

Backlog
→ In Progress

Текущий статус:

In Progress

---

### BUG-1

Bug

SP: 3

Workflow:

To Do

Текущий статус:

To Do

---

## Ожидаемые метрики

Done issues:

0

High WIP:

YES

Velocity:

0

Completion rate:

низкий

---

# PROJECT 3 — MIXED

Цель:

Проверка realistic production scenario.

Ожидаем:

- часть задач завершена
- часть в работе
- часть в backlog
- смешанные assignees
- mixed transitions

---

## Сценарии задач

### TASK-1

Task

SP: 5

Workflow:

Backlog
→ To Do
→ In Progress
→ Done

---

### TASK-2

Task

SP: 8

Workflow:

Backlog
→ In Progress

---

### BUG-1

Bug

SP: 2

Workflow:

To Do
→ Done

---

### SUBTASK-1

Subtask

SP: 1

Workflow:

To Do
→ In Progress

---

## Ожидаемые метрики

Velocity:

7

WIP:

есть

Completion rate:

средний