from abc import ABC, abstractmethod
from typing import List, Dict


class BaseAIProvider(ABC):

    @abstractmethod
    async def generate_insights(
        self,
        projects_data: List[Dict]
    ) -> List[Dict]:
        pass

    async def chat_completions(
        self,
        messages: List[Dict]
    ) -> str:
        """
        Базовая реализация chat completions (может быть переопределена в подклассах)
        """
        raise NotImplementedError("chat_completions not implemented")

