import json
import httpx
from app.services.ai.base import BaseAIProvider

class OpenRouterProvider(BaseAIProvider):

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    async def generate_insights(self, projects_data: list) -> list:

        prompt = f"""
        Ты AI-аналитик проектов.

        Анализируй данные Jira и возвращай выводы ТОЛЬКО на русском языке.

        Верни только JSON.
        Не используй markdown.
        Не используй ```json.
        Не добавляй пояснений вне JSON.

        Формат:
        [
        {{
            "id": 1,
            "type": "warning",
            "text": "...",
            "recommendation": "..."
        }}
        ]

        Данные:
        {json.dumps(projects_data, ensure_ascii=False)}
        """

        async with httpx.AsyncClient(timeout=60) as client:

            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                }
            )

            data = response.json()

            # ЛОГИ ДЛЯ ОТЛАДКИ
            print("OPENROUTER RESPONSE:")
            print(json.dumps(data, indent=2, ensure_ascii=False))

            # Проверка ошибок
            if "choices" not in data:
                raise Exception(
                    f"OpenRouter error: {json.dumps(data, ensure_ascii=False)}"
                )

            content = data["choices"][0]["message"]["content"]
            # remove markdown wrappers
            content = content.replace("```json", "")
            content = content.replace("```", "")
            content = content.strip()

            try:
                return json.loads(content)
            except Exception:
                return [
                    {
                        "id": 1,
                        "type": "warning",
                        "text": content,
                        "recommendation": "AI вернул текст вместо JSON"
                    }
                ]