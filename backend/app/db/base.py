#backend/app/db/base.py
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# Импортируем все модели, чтобы Alembic их видел
# Это важно для autogenerate миграций!