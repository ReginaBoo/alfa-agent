from app.db.session import SessionLocal
import datetime
from datetime import timedelta

from app.db.models import IntegrationToken 

def save_token(user_id, cloud_id, data):
    db = SessionLocal()
    token = IntegrationToken(  # было: Token
        user_id=user_id,
        cloud_id=cloud_id,
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        expires_at=datetime.datetime.utcnow() + timedelta(seconds=data["expires_in"])
    )
    db.add(token) 
    db.commit()
    db.close()