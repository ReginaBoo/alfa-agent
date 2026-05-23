"""
Сервис кэширования с использованием Redis.
"""
import json
import logging
from typing import Optional, Any, Callable
from datetime import timedelta
import redis

from app.core.config import settings

logger = logging.getLogger(__name__)


class CacheService:
    """Сервис кэширования в Redis"""
    
    def __init__(self, redis_url: str = None):
        self.redis_client = redis.from_url(
            redis_url or settings.REDIS_URL,
            decode_responses=True
        )
    
    def get(self, key: str) -> Optional[Any]:
        """Получает значение из кэша"""
        try:
            data = self.redis_client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Cache get error for {key}: {e}")
            return None
    
    def set(self, key: str, value: Any, expire: int = 300) -> bool:
        """
        Сохраняет значение в кэш.
        
        Args:
            key: Ключ кэша
            value: Значение (сериализуемое в JSON)
            expire: Время жизни в секундах (по умолчанию 5 минут)
        """
        try:
            serialized = json.dumps(value, ensure_ascii=False, default=str)
            self.redis_client.setex(key, expire, serialized)
            return True
        except Exception as e:
            logger.error(f"Cache set error for {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Удаляет ключ из кэша"""
        try:
            self.redis_client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error for {key}: {e}")
            return False
    
    def delete_pattern(self, pattern: str) -> bool:
        """
        Удаляет все ключи, matching паттерну.
        Например: cache.delete_pattern("ai_insights:*")
        """
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
            return True
        except Exception as e:
            logger.error(f"Cache delete_pattern error for {pattern}: {e}")
            return False
    
    def clear_all(self) -> bool:
        """Очищает весь кэш (осторожно!)"""
        try:
            self.redis_client.flushdb()
            return True
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """Проверяет是否存在 ключ в кэше"""
        try:
            return self.redis_client.exists(key) > 0
        except Exception as e:
            logger.error(f"Cache exists error for {key}: {e}")
            return False
    
    def get_or_set(
        self,
        key: str,
        factory: Callable,
        expire: int = 300
    ) -> Any:
        """
        Получает значение из кэша или вычисляет и сохраняет.
        
        Args:
            key: Ключ кэша
            factory: Функция для вычисления значения (ленняя оценка)
            expire: Время жизни в секундах
        """
        # Пробуем получить из кэша
        cached = self.get(key)
        if cached is not None:
            logger.debug(f"Cache HIT for {key}")
            return cached
        
        # Вычисляем заново
        logger.debug(f"Cache MISS for {key}, computing...")
        value = factory()
        
        # Сохраняем в кэш
        self.set(key, value, expire)
        
        return value


# Глобальный экземпляр
cache_service = CacheService()
