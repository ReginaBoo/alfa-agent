"""
Сервис для синхронизации страниц из Confluence в БД.
"""

import logging
from datetime import datetime
from sqlalchemy.orm import Session
from app.db.models import IntegrationToken, RawEvent
from app.db.models.normalized import ConfluencePage
from app.confluence.client import ConfluenceClient
from app.services.token_service import TokenService

logger = logging.getLogger(__name__)


def make_serializable(obj):
    """Рекурсивно преобразует datetime в строку ISO формата"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: make_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_serializable(item) for item in obj]
    return obj


class ConfluenceSyncService:
    """Синхронизация данных из Confluence в БД"""

    def __init__(self, db: Session):
        self.db = db

    async def sync_space_pages(
        self,
        user_id: int,
        instance_name: str,
        space_id: str,
        space_key: str = None
    ) -> dict:
        """Синхронизирует все страницы из пространства Confluence"""
        
        logger.info(f"Starting sync for space {space_id}, instance {instance_name}")
        
        token = self.db.query(IntegrationToken).filter(
            IntegrationToken.user_id == user_id,
            IntegrationToken.instance_name == instance_name,
            IntegrationToken.provider == "jira"
        ).first()

        if not token:
            raise ValueError(f"Token not found for site {instance_name}")
        
        logger.info(f"Token found for {token.instance_name}")
        
        token_service = TokenService(self.db)
        client = ConfluenceClient(token_service)
        cloud_id = token.instance_id
        
        created_count = 0
        updated_count = 0
        
        start = 0
        limit = 25
        
        while True:
            logger.info(f"Fetching pages, start={start}, limit={limit}")
            try:
                pages = await client.get_pages_by_space(
                    cloud_id=cloud_id,
                    space_id=space_id,
                    limit=limit,
                    start=start,
                    user_id=user_id
                )
                logger.info(f"Got {len(pages)} pages")
            except Exception as e:
                logger.error(f"Failed to fetch pages: {e}")
                raise
            
            if not pages:
                break
            
            for idx, page in enumerate(pages):
                logger.info(f"Processing page {idx+1}: id={page.id}, title={page.title}")
                page_id = page.id
                
                created_at = page.created_at
                updated_at = page.version.created_at if page.version else None
                
                try:
                    content_data = await client.get_page_content(
                        cloud_id=cloud_id,
                        page_id=page_id,
                        format="storage",
                        user_id=user_id
                    )
                    content = content_data.get("value", "")
                    logger.info(f"Got content for page {page_id}, length={len(content)}")
                except Exception as e:
                    logger.warning(f"Failed to get content for page {page_id}: {e}")
                    content = ""
                
                # Сериализуем payload
                try:
                    serializable_page = make_serializable(page.dict())
                    logger.info(f"Serialized page {page_id}")
                except Exception as e:
                    logger.error(f"Failed to serialize page {page_id}: {e}")
                    raise
                
                try:
                    raw_event = RawEvent(
                        source="confluence",
                        event_type="page",
                        external_id=page_id,
                        project_integration_id=None,
                        payload=serializable_page,
                        timestamp=datetime.utcnow()
                    )
                    self.db.add(raw_event)
                    logger.info(f"Added raw_event for page {page_id}")
                except Exception as e:
                    logger.error(f"Failed to create raw_event: {e}")
                    raise
                
                try:
                    existing = self.db.query(ConfluencePage).filter(
                        ConfluencePage.id == page_id
                    ).first()
                    
                    if existing:
                        existing.title = page.title
                        existing.updated_at = updated_at or datetime.utcnow()
                        existing.version = page.version.number if page.version else 1
                        existing.content = content
                        existing.last_synced_at = datetime.utcnow()
                        updated_count += 1
                        logger.info(f"Updated page {page_id}")
                    else:
                        new_page = ConfluencePage(
                            id=page_id,
                            space_id=space_id,
                            space_key=space_key,
                            title=page.title,
                            author_id=page.author_id,
                            version=page.version.number if page.version else 1,
                            status=page.status,
                            parent_id=page.parent_id,
                            created_at=created_at or datetime.utcnow(),
                            updated_at=updated_at or datetime.utcnow(),
                            content=content,
                            last_synced_at=datetime.utcnow()
                        )
                        self.db.add(new_page)
                        created_count += 1
                        logger.info(f"Created page {page_id}")
                except Exception as e:
                    logger.error(f"Failed to save page {page_id}: {e}")
                    raise
                
                try:
                    self.db.commit()
                    logger.info(f"Committed page {page_id}")
                except Exception as e:
                    logger.error(f"Failed to commit: {e}")
                    raise
            
            start += limit
            if len(pages) < limit:
                break
        
        logger.info(f"Sync completed: created={created_count}, updated={updated_count}")
        return {
            "created": created_count,
            "updated": updated_count,
            "total": created_count + updated_count,
            "space_id": space_id,
            "instance_name": instance_name
        }