# app/services/token_service.py
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.db.models import AtlassianToken


def save_tokens_for_working_sites(
    db: Session,
    user_id: int,
    atlassian_account_id: str,
    token_data,
    working_sites: list,
    expires_at: datetime
) -> list:
    """Сохраняет токены для рабочих сайтов"""
    saved_tokens = []
    
    for resource in working_sites:
        cloud_id = resource["id"]
        site_url = resource["url"]
        site_name = resource.get("name", "")
        
        existing_token = db.query(AtlassianToken).filter(
            AtlassianToken.user_id == user_id,
            AtlassianToken.cloud_id == cloud_id
        ).first()
        
        if existing_token:
            existing_token.access_token = token_data.access_token
            existing_token.refresh_token = token_data.refresh_token
            existing_token.expires_at = expires_at
            existing_token.site_url = site_url
            existing_token.site_name = site_name
            db.commit()
            db.refresh(existing_token)
            saved_tokens.append(existing_token)
            print(f"Updated token for site: {site_name}")
        else:
            db_token = AtlassianToken(
                user_id=user_id,
                atlassian_account_id=atlassian_account_id,
                access_token=token_data.access_token,
                refresh_token=token_data.refresh_token,
                cloud_id=cloud_id,
                site_url=site_url,
                site_name=site_name,
                expires_at=expires_at
            )
            db.add(db_token)
            db.commit()
            db.refresh(db_token)
            saved_tokens.append(db_token)
            print(f"Created new token for site: {site_name}")
    
    return saved_tokens