from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from datetime import datetime

from app.db.base import Base


class Token(Base):
    __tablename__ = "tokens"

    id = Column(Integer, primary_key=True, index=True)

    # пользователь (пока можно просто строкой)
    user_id = Column(String, index=True)

    # Atlassian
    access_token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=False)

    # сайт (ключевой момент!)
    cloud_id = Column(String, index=True)
    site_url = Column(String)

    # срок жизни
    expires_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)