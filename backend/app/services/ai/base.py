from abc import ABC, abstractmethod
from typing import List, Dict


class BaseAIProvider(ABC):

    @abstractmethod
    async def generate_insights(
        self,
        projects_data: List[Dict]
    ) -> List[Dict]:
        pass