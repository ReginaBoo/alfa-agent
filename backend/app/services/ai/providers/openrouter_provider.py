import json
import httpx
import logging
from typing import List, Dict, Any
from app.services.ai.base import BaseAIProvider

logger = logging.getLogger(__name__)


class OpenRouterProvider(BaseAIProvider):

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    async def generate_insights(self, projects_data: list) -> list:
        """
        Дополнительная генерация инсайтов через LLM (опционально).
        Пока возвращает пустой список, т.к. основная логика в insight_service.py
        """
        return []

    async def chat_completions(self, messages: List[Dict[str, str]]) -> str:
        """
        Вызывает OpenRouter API для получения ответа чата
        
        Args:
            messages: Список сообщений в формате [{"role": "user/assistant/system", "content": "..."}]
            
        Returns:
            Текст ответа AI
        """
        url = "https://openrouter.ai/api/v1/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "Alpha Agent"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1000
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                
                result = response.json()
                answer = result["choices"][0]["message"]["content"]
                
                logger.info(f"AI response received: {len(answer)} chars")
                return answer
                
        except httpx.HTTPError as e:
            logger.error(f"OpenRouter API error: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in chat_completions: {e}")
            raise