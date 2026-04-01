# app/tasks/refresh_tokens.py
import asyncio
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models import AtlassianToken
from app.services.token_refresh_service import TokenRefreshService


async def refresh_expiring_tokens():
    """Фоновая задача: обновляет токены, которые истекают в ближайший час"""
    while True:
        db = SessionLocal()
        try:
            # Находим токены, которые истекут в ближайший час
            expiring_soon = datetime.utcnow() + timedelta(hours=1)
            
            tokens = db.query(AtlassianToken).filter(
                AtlassianToken.expires_at <= expiring_soon
            ).all()
            
            # Группируем по user_id
            user_ids = set(t.user_id for t in tokens)
            
            for user_id in user_ids:
                success = TokenRefreshService.update_user_tokens(db, user_id)
                if success:
                    print(f"Refreshed tokens for user {user_id}")
                else:
                    print(f"Failed to refresh tokens for user {user_id}")
            
            db.commit()
            
        except Exception as e:
            print(f"Error in refresh task: {e}")
        finally:
            db.close()
        
        # Ждем 30 минут перед следующей проверкой
        await asyncio.sleep(1800)


# В main.py запускаем фоновую задачу
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(refresh_expiring_tokens())