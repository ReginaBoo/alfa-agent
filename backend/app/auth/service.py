from app.db.session import SessionLocal
from app.db.models import Token
import datetime

def save_token(user_id, cloud_id, data):
    db = SessionLocal()

    token = Token(
        id=cloud_id,
        user_id=user_id,
        cloud_id=cloud_id,
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(seconds=data["expires_in"])
    )

    db.merge(token)
    db.commit()
    db.close()