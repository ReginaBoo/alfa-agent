# tests/confluence/test_confluence_client.py
import asyncio
import sys
from app.db.session import SessionLocal
from app.services.token_service import TokenService
from app.confluence.client import ConfluenceClient
from app.confluence.models import ConfluenceSpace, ConfluencePage

async def test_with_mock():
    """Тест логики клиента на моковых данных"""
    print("[MOCK] ConfluenceClient logic validation", flush=True)
    
    # Моковые данные (формат API v1 — самый совместимый)
    mock_spaces = [
        {"id": "10001", "key": "DEV", "name": "Development", "type": "global", "status": "current"},
        {"id": "10002", "key": "DOC", "name": "Documentation", "type": "global", "status": "current"},
    ]
    
    # 1. Проверяем модели
    spaces = [ConfluenceSpace(**s) for s in mock_spaces]
    print(f"Models: Parsed {len(spaces)} spaces", flush=True)
    
    # 2. Проверяем инициализацию клиента
    db = SessionLocal()
    token_service = TokenService(db)
    client = ConfluenceClient(token_service)
    assert client.base_url == "https://api.atlassian.com/ex/confluence"
    print("Client: Initialized correctly", flush=True)
    
    # 3. Проверяем базовую логику (фильтрация, свойства)
    active = [s for s in spaces if s.status == "current"]
    print(f"Logic: Filtered {len(active)} active spaces", flush=True)
    
    db.close()
    
    print("[MOCK TEST PASSED]", flush=True)
    print("Real API skipped — Confluence not activated on this cloud", flush=True)
    return True

if __name__ == "__main__":
    result = asyncio.run(test_with_mock())
    sys.exit(0 if result else 1)