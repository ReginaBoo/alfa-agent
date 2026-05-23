import json
import httpx
from app.services.ai.base import BaseAIProvider

class OpenRouterProvider(BaseAIProvider):

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    async def generate_insights(self, projects_data: list) -> list:
        """
        Дополнительная генерация инсайтов через LLM (опционально).
        Пока возвращает пустой список, т.к. основная логика в insight_service.py
        """
        # Можно использовать для генерации дополнительных инсайтов на основе агрегированных данных
        # Пока возвращаем пустой список, т.к. все инсайты генерируются в AIInsightService
        return []