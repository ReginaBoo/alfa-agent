import httpx
import logging
from typing import List, Dict

from app.services.ai.base import BaseAIProvider

logger = logging.getLogger(__name__)


class AlphaBankProvider(BaseAIProvider):

    def __init__(
        self,
        model: str,
        api_url: str,
        api_key: str | None = None
    ):
        self.model = model
        self.api_url = api_url
        self.api_key = api_key

    async def generate_insights(self, projects_data: list) -> list:
        return []

    async def chat_completions(
        self,
        messages: List[Dict[str, str]]
    ) -> str:

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "temperature": 1
        }

        headers = {
            "Content-Type": "application/json"
        }

        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.api_url,
                    json=payload,
                    headers=headers
                )

                response.raise_for_status()

                result = response.json()

                answer = result["choices"][0]["message"]["content"]

                logger.info(
                    f"AlphaBank response received: {len(answer)} chars"
                )

                return answer

        except Exception as e:
            logger.error(f"AlphaBank API error: {e}")
            raise