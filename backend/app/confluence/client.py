# app/confluence/client.py
import logging

import httpx
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.core.config import settings
from app.services.token_service import TokenService
from app.confluence.models import ConfluencePage, ConfluenceSpace, ConfluencePageVersion

logger = logging.getLogger(__name__)
class ConfluenceClient:
    """Клиент для Confluence API с авто-обновлением токенов"""
    
    def __init__(self, token_service: TokenService):
        self.token_service = token_service
        self.base_url = "https://api.atlassian.com/ex/confluence"
        self.timeout = httpx.Timeout(30.0)
    
    async def _request(
        self,
        cloud_id: str,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Внутренний метод запроса (аналогично JiraClient)"""
        token = self.token_service.get_valid_token(
            user_id=user_id,
            provider="jira",  # или "confluence"
            instance_id=cloud_id
        )
        
        if not token:
            raise ValueError(f"No valid token for Confluence cloud_id {cloud_id}")
        
        url = f"{self.base_url}/{cloud_id}{endpoint}"
        headers = {
            "Authorization": f"Bearer {token.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json
            )
            
            # Авто-обновление токена при 401
            if response.status_code == 401:
                self.token_service._refresh_and_update(user_id)
                token = self.token_service.get_valid_token(
                    user_id=user_id,
                    provider="jira",  # или "confluence"
                    instance_id=cloud_id
                )
                headers["Authorization"] = f"Bearer {token.access_token}"
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=json
                )
            
            response.raise_for_status()
            return response.json()
    
    async def get_spaces(
        self,
        cloud_id: str,
        user_id: Optional[int] = None
    ) -> List[ConfluenceSpace]:
        """Получает список пространств"""
        data = await self._request(
            cloud_id=cloud_id,
            endpoint="/wiki/api/v2/spaces",
            method="GET",
            user_id=user_id
        )
        return [ConfluenceSpace(**space) for space in data.get("results", [])]
    


    async def get_pages(
        self,
        cloud_id: str,
        limit: int = 25,
        start: int = 0,
        expand: str = "version,space",
        user_id: Optional[int] = None
    ) -> List[ConfluencePage]:
        """Получает страницы с пагинацией (со всех пространств)"""
        params = {
            "limit": limit,
            "start": start,
            "expand": expand
        }
        
        data = await self._request(
            cloud_id=cloud_id,
            endpoint="/wiki/api/v2/pages",
            method="GET",
            params=params,
            user_id=user_id
        )
    
        return [ConfluencePage(**page) for page in data.get("results", [])]
    
    async def get_pages_by_space(
        self,
        cloud_id: str,
        space_id: str,
        limit: int = 25,
        start: int = 0,
        expand: str = "version,space",
        user_id: Optional[int] = None
    ) -> List[ConfluencePage]:
        """Получает страницы из пространства с пагинацией"""
        params = {
            "limit": limit,
            "start": start,
            "expand": expand
        }
        
        data = await self._request(
            cloud_id=cloud_id,
            endpoint=f"/wiki/api/v2/spaces/{space_id}/pages",
            method="GET",
            params=params,
            user_id=user_id
        )
        
        return [ConfluencePage(**page) for page in data.get("results", [])]
    
    async def get_page_content(
        self,
        cloud_id: str,
        page_id: str,
        format: str = "storage",
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Получает содержимое страницы через API v2"""
        params = {
            "body-format": format,
            "include-version": "true"
        }
        
        data = await self._request(
            cloud_id=cloud_id,
            endpoint=f"/wiki/api/v2/pages/{page_id}",
            method="GET",
            params=params,
            user_id=user_id
        )
        
        # Извлекаем тело страницы
        body = data.get("body", {})
        return body.get(format, {})
    
    async def search_pages_cql(
        self,
        cloud_id: str,
        cql: str,
        limit: int = 25,
        start: int = 0,
        user_id: Optional[int] = None
    ) -> List[ConfluencePage]:
        """Поиск страниц через CQL (Confluence Query Language)"""
        params = {
            "cql": cql,
            "limit": limit,
            "start": start,
            "expand": "version,space"
        }
        
        data = await self._request(
            cloud_id=cloud_id,
            endpoint="/wiki/api/v2/search",
            method="GET",
            params=params,
            user_id=user_id
        )
        
        return [ConfluencePage(**page) for page in data.get("results", [])]
    
    async def get_page_history(
        self,
        cloud_id: str,
        page_id: str,
        user_id: Optional[int] = None
    ) -> List[ConfluencePageVersion]:
        """Получает историю версий страницы"""
        data = await self._request(
            cloud_id=cloud_id,
            endpoint=f"/wiki/api/v2/pages/{page_id}/versions",
            method="GET",
            user_id=user_id
        )
        
        return [ConfluencePageVersion(**v) for v in data.get("results", [])]
    
    async def get_page_comments(
        self,
        cloud_id: str,
        page_id: str,
        user_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Получает комментарии к странице.
        Возвращает сырой список — структура комментариев в Confluence сложная.
        """
        data = await self._request(
            cloud_id=cloud_id,
            endpoint=f"/wiki/api/v2/pages/{page_id}/comments",
            method="GET",
            user_id=user_id
        )
        
        return data.get("results", [])
    
    async def get_page_versions(
        self,
        cloud_id: str,
        page_id: str,
        user_id: int
    ) -> list[dict]:
        """
        Выгружает ВСЮ историю версий страницы через пагинацию.
        """
        versions = []
        start = 0
        limit = 50

        while True:
            data = await self._request(
                cloud_id=cloud_id,
                endpoint=f"/wiki/api/v2/pages/{page_id}/versions",
                method="GET",
                params={
                    "limit": limit,
                    "start": start
                },
                user_id=user_id
            )

            batch = data.get("results", [])
            if not batch:
                break

            versions.extend(batch)

            if len(batch) < limit:
                break

            start += limit

        return versions
    
    async def get_page_comments(
        self,
        cloud_id: str,
        page_id: str,
        user_id: int
    ) -> list[dict]:
        """
        Выгружает ВСЕ комментарии страницы:
        footer-comments + inline-comments.
        """
        all_comments = []

        for endpoint in [
            f"/wiki/api/v2/pages/{page_id}/footer-comments",
            f"/wiki/api/v2/pages/{page_id}/inline-comments"
        ]:
            start = 0
            limit = 50

            while True:
                try:
                    data = await self._request(
                        cloud_id=cloud_id,
                        endpoint=endpoint,
                        method="GET",
                        params={
                            "limit": limit,
                            "start": start,
                            "body-format": "storage"
                        },
                        user_id=user_id
                    )
                except Exception as e:
                    logger.warning(f"Comment endpoint failed {endpoint}: {e}")
                    break

                batch = data.get("results", [])
                if not batch:
                    break

                all_comments.extend(batch)

                if len(batch) < limit:
                    break

                start += limit

        return all_comments