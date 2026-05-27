#!/bin/bash
# Тест Задачи 3: Фоновый сбор задач из Jira (Windows/GitBash safe)

set -euo pipefail

SESSION_TOKEN="${1:-}"
INSTANCE="${2:-reginaboo}"
BASE_URL="http://localhost:8000"

if [ -z "$SESSION_TOKEN" ]; then
    echo "Usage: $0 <session_token> [instance_name]"
    exit 1
fi

# -----------------------------
# Docker compose detection
# -----------------------------
if docker-compose version >/dev/null 2>&1; then
    DB_CMD="docker-compose exec -T db"
elif docker compose version >/dev/null 2>&1; then
    DB_CMD="docker compose exec -T db"
else
    echo "❌ Docker Compose недоступен"
    exit 1
fi

# -----------------------------
# JSON parser через Python
# -----------------------------
parse_json() {
    local json="$1"
    local mode="$2"

    JSON_INPUT="$json" python - "$mode" <<'PY'
import json
import os
import sys

mode = sys.argv[1]
raw = os.environ.get("JSON_INPUT", "")

try:
    data = json.loads(raw)
except Exception as e:
    print("")
    sys.exit(1)

if mode == "project_keys":
    for p in data.get("projects", []):
        print(p.get("key", ""))

elif mode == "job_id":
    print(data.get("data", {}).get("job_id", ""))

elif mode == "status":
    print(data.get("data", {}).get("status", "unknown"))

elif mode == "details":
    result = data.get("data", {}).get("result", {})
    if isinstance(result, dict):
        print(json.dumps(result.get("details", result), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))

elif mode == "error":
    err = data.get("data", {}).get("error", data.get("data", {}))
    print(json.dumps(err, ensure_ascii=False, indent=2))
PY
}

# -----------------------------
# Шаг 1
# -----------------------------
echo "🔍 Шаг 1: Получаем список проектов..."

PROJECTS_JSON=$(curl -s "$BASE_URL/jira/projects?instance_name=$INSTANCE&sync_to_db=false" \
    -b "session_token=$SESSION_TOKEN")

if [[ "$PROJECTS_JSON" != *'"success":true'* ]]; then
    echo "❌ Ошибка получения проектов:"
    echo "$PROJECTS_JSON"
    exit 1
fi

PROJECT_KEYS=$(parse_json "$PROJECTS_JSON" "project_keys" | tr -d '\r')

if [ -z "$PROJECT_KEYS" ]; then
    echo "❌ Нет проектов для тестирования"
    echo "$PROJECTS_JSON"
    exit 1
fi

echo "✅ Проекты найдены: $(printf '%s\n' "$PROJECT_KEYS" | tr '\n' ' ')"

FIRST_PROJECT=$(printf '%s\n' "$PROJECT_KEYS" | head -n 1 | tr -d '\r')

if [ -z "$FIRST_PROJECT" ]; then
    echo "❌ Не удалось определить проект"
    exit 1
fi

echo "🎯 Тестируем проект: $FIRST_PROJECT"

# -----------------------------
# Шаг 2
# -----------------------------
echo
echo "🔍 Шаг 2: Запускаем синхронизацию одного проекта..."

SYNC_RESP=$(curl -s -X POST "$BASE_URL/jira/sync-async/$FIRST_PROJECT?instance_name=$INSTANCE" \
    -b "session_token=$SESSION_TOKEN")

if [[ "$SYNC_RESP" != *'"job_id"'* ]]; then
    echo "❌ Не удалось получить job_id"
    echo "$SYNC_RESP"
    exit 1
fi

JOB_ID=$(parse_json "$SYNC_RESP" "job_id" | tr -d '\r')

if [ -z "$JOB_ID" ] || [ "$JOB_ID" = "null" ]; then
    echo "❌ job_id пустой"
    echo "$SYNC_RESP"
    exit 1
fi

echo "✅ Задача запущена: job_id=$JOB_ID"

# -----------------------------
# Шаг 3
# -----------------------------
echo
echo "🔍 Шаг 3: Ждём выполнения задачи (до 60 секунд)..."

TASK_FINISHED=false

for i in {1..12}; do
    STATUS_RESP=$(curl -s "$BASE_URL/job/$JOB_ID")
    STATUS=$(parse_json "$STATUS_RESP" "status" | tr -d '\r')

    echo "  Попытка $i: статус = $STATUS"

    if [ "$STATUS" = "finished" ]; then
        echo "✅ Задача выполнена!"
        parse_json "$STATUS_RESP" "details"
        TASK_FINISHED=true
        break
    elif [ "$STATUS" = "failed" ]; then
        echo "❌ Задача завершилась с ошибкой:"
        parse_json "$STATUS_RESP" "error"
        exit 1
    fi

    sleep 5
done

if [ "$TASK_FINISHED" = false ]; then
    echo "❌ Таймаут ожидания выполнения фоновой задачи"
    exit 1
fi

# -----------------------------
# Шаг 4
# -----------------------------
echo
echo "🔍 Шаг 4: Проверяем данные в БД..."

$DB_CMD psql -U postgres -d app_db -c \
"SELECT project_key, COUNT(*) as total
 FROM normalized.jira_issues
 WHERE project_key='$FIRST_PROJECT'
 GROUP BY project_key;"

echo
echo "🎉 Тест Задачи 3 завершён успешно!"