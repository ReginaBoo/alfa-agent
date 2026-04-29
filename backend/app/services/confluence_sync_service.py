"""
Сервис для синхронизации страниц из Confluence в БД.
Полная реализация: пагинация, raw_events, версии, комментарии.
"""
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.db.models import IntegrationToken, RawEvent
from app.db.models.normalized import ConfluencePage, ConfluencePageVersion, ConfluenceComment
from app.confluence.client import ConfluenceClient
from app.services.token_service import TokenService

logger = logging.getLogger(__name__)


def make_serializable(obj: Any) -> Any:
    """Рекурсивно преобразует datetime в ISO-строку для JSON"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: make_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_serializable(item) for item in obj]
    return obj


def extract_comment_body(body: Dict[str, Any]) -> str:
    """Извлекает текст комментария из структуры API v2"""
    if not body:
        return ""
    # API v2: body -> storage -> value (HTML)
    storage = body.get("storage", {})
    value = storage.get("value", "")
    # Простая очистка от HTML (можно улучшить)
    import re
    clean = re.sub(r'<[^>]+>', '', value)
    return clean.strip()


class ConfluenceSyncService:
    """Синхронизация данных из Confluence в БД"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def sync_space_pages(
        self,
        user_id: int,
        instance_name: str,
        space_id: str,
        space_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Синхронизирует ВСЕ страницы из пространства Confluence.
        
        Реализует:
        1. Пагинацию (выгружает все страницы, не только первую порцию)
        2. Сохранение сырых ответов в raw_events
        3. Нормализацию в confluence_pages
        4. Сохранение истории версий в confluence_page_versions
        5. Сохранение комментариев в confluence_comments
        """
        logger.info(f"Starting sync for space {space_id} ({space_key}), instance {instance_name}")
        
        # 1. Получаем токен
        token = self.db.query(IntegrationToken).filter(
            IntegrationToken.user_id == user_id,
            IntegrationToken.instance_name == instance_name,
            IntegrationToken.provider == "jira"  # единый токен для Jira/Confluence
        ).first()
        
        if not token:
            raise ValueError(f"Token not found for site {instance_name}")
        
        # 2. Инициализируем клиент
        token_service = TokenService(self.db)
        client = ConfluenceClient(token_service)
        cloud_id = token.instance_id
        
        # Счётчики для результата
        stats = {
            "pages_created": 0,
            "pages_updated": 0,
            "versions_saved": 0,
            "comments_saved": 0,
            "errors": 0
        }
        
        # 3. ПАГИНАЦИЯ: выгружаем все страницы порциями
        start = 0
        limit = 25  # максимум по API v2
        
        while True:
            logger.info(f"Fetching pages: space={space_id}, start={start}, limit={limit}")
            
            try:
                pages = await client.get_pages_by_space(
                    cloud_id=cloud_id,
                    space_id=space_id,
                    limit=limit,
                    start=start,
                    expand="version,space,body.storage",
                    user_id=user_id
                )
            except Exception as e:
                logger.error(f"Failed to fetch pages: {e}")
                stats["errors"] += 1
                break
            
            if not pages:
                logger.info("No more pages to fetch")
                break
            
            logger.info(f"Fetched {len(pages)} pages")
            
            # 4. Обрабатываем каждую страницу
            for page in pages:
                try:
                    await self._sync_single_page(
                        client=client,
                        cloud_id=cloud_id,
                        page=page,
                        space_key=space_key,
                        user_id=user_id,
                        stats=stats
                    )
                except Exception as e:
                    logger.error(f"Failed to sync page {page.id}: {e}")
                    stats["errors"] += 1
                    continue
            
            # Проверяем, есть ли ещё страницы
            if len(pages) < limit:
                logger.info("Last page reached")
                break
            
            start += limit
        
        # 5. Финальный коммит
        self.db.commit()
        
        logger.info(f"Sync completed for space {space_id}: {stats}")
        return {
            "space_id": space_id,
            "space_key": space_key,
            "instance_name": instance_name,
            **stats
        }
    
    async def _sync_single_page(
        self,
        client,
        cloud_id: str,
        page,
        space_key: Optional[str],
        user_id: int,
        stats: Dict[str, int]
    ) -> None:

        page_id = str(page.id)

        # =========================================================
        # 1. RAW PAGE EVENT
        # =========================================================
        existing_raw = self.db.query(RawEvent).filter(
            RawEvent.source == "confluence",
            RawEvent.event_type == "page",
            RawEvent.external_id == page_id
        ).first()

        if not existing_raw:
            self.db.add(RawEvent(
                source="confluence",
                event_type="page",
                external_id=page_id,
                project_integration_id=None,
                payload=make_serializable(page.dict()),
                timestamp=datetime.utcnow()
            ))

        # =========================================================
        # 2. PAGE CONTENT
        # =========================================================
        content = ""
        try:
            content_data = await client.get_page_content(
                cloud_id=cloud_id,
                page_id=page_id,
                format="storage",
                user_id=user_id
            )
            storage = content_data.get("storage", {})
            html = storage.get("value", "")

            import re
            content = re.sub(r"<[^>]+>", "", html).strip()
        except Exception as e:
            logger.warning(f"Content fetch failed for page {page_id}: {e}")

        # =========================================================
        # 3. UPSERT NORMALIZED PAGE
        # =========================================================
        existing_page = self.db.query(ConfluencePage).filter(
            ConfluencePage.id == page_id
        ).first()

        current_version = getattr(page.version, "number", 1) if hasattr(page, "version") else 1
        current_updated = getattr(page.version, "created_at", datetime.utcnow()) if hasattr(page, "version") else datetime.utcnow()

        if existing_page:
            existing_page.title = page.title
            existing_page.space_key = space_key
            existing_page.version = current_version
            existing_page.updated_at = current_updated
            existing_page.content = content
            existing_page.last_synced_at = datetime.utcnow()
            stats["pages_updated"] += 1
        else:
            self.db.add(ConfluencePage(
                id=page_id,
                space_id=str(page.space_id),
                space_key=space_key,
                title=page.title,
                author_id=getattr(page, "author_id", None),
                author_name=None,
                version=current_version,
                status=getattr(page, "status", "current"),
                parent_id=getattr(page, "parent_id", None),
                created_at=getattr(page, "created_at", datetime.utcnow()),
                updated_at=current_updated,
                content=content,
                last_synced_at=datetime.utcnow()
            ))
            stats["pages_created"] += 1

        self.db.commit()

        # =========================================================
        # 4. FULL VERSION HISTORY
        # =========================================================
        try:
            versions = await client.get_page_versions(
                cloud_id=cloud_id,
                page_id=page_id,
                user_id=user_id
            )

            for version in versions:
                existing_version = self.db.query(ConfluencePageVersion).filter(
                    ConfluencePageVersion.page_id == page_id,
                    ConfluencePageVersion.version_number == version.get("number")
                ).first()

                if existing_version:
                    continue

                self.db.add(ConfluencePageVersion(
                    page_id=page_id,
                    version_number=version.get("number"),
                    message=version.get("message"),
                    author_id=version.get("authorId"),
                    author_name=version.get("authorName"),
                    created_at=version.get("createdAt"),
                    minor_edit=version.get("minorEdit", False)
                ))
                stats["versions_saved"] += 1

        except Exception as e:
            logger.warning(f"Versions fetch failed for page {page_id}: {e}")
            stats["errors"] += 1

        # =========================================================
        # 5. COMMENTS
        # =========================================================
        try:
            comments = await client.get_page_comments(
                cloud_id=cloud_id,
                page_id=page_id,
                user_id=user_id
            )

            for comment in comments:
                comment_id = str(comment.get("id"))

                existing_comment = self.db.query(ConfluenceComment).filter(
                    ConfluenceComment.id == comment_id
                ).first()

                if existing_comment:
                    continue

                body_text = extract_comment_body(comment.get("body", {}))

                self.db.add(ConfluenceComment(
                    id=comment_id,
                    page_id=page_id,
                    author_id=comment.get("version", {}).get("authorId"),
                    author_name=comment.get("version", {}).get("authorName"),
                    body=body_text,
                    created_at=comment.get("version", {}).get("createdAt"),
                    updated_at=comment.get("version", {}).get("createdAt"),
                    is_resolved=False,
                    parent_id=comment.get("parentCommentId"),
                    position=comment.get("resolutionStatus", "footer")
                ))

                stats["comments_saved"] += 1

        except Exception as e:
            logger.warning(f"Comments fetch failed for page {page_id}: {e}")
            stats["errors"] += 1

        self.db.commit()