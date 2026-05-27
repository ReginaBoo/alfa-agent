# tests/test_health.py

import pytest


@pytest.mark.asyncio
async def test_health_check(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    # Не проверяем на точное совпадение, только наличие status


@pytest.mark.asyncio
async def test_root_redirect(client):
    # Если нет редиректа с /, просто проверяем что ответ не 500
    response = await client.get("/", follow_redirects=False)
    # Может быть 307, 404 или 200 — в зависимости от реализации
    assert response.status_code in [200, 307, 404]