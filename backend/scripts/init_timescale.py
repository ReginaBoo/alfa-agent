# backend/scripts/init_timescale.py

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.timescale import timescale_engine, TimescaleBase
from app.db.models.metrics import *
from sqlalchemy import text

def init_timescale():
    print("Инициализация TimescaleDB...")
    
    # Создаем таблицы
    TimescaleBase.metadata.create_all(bind=timescale_engine)
    print("Таблицы метрик созданы")
    
    # Создаем гипертаблицу
    with timescale_engine.connect() as conn:
        conn.execute(text("""
            SELECT create_hypertable('metrics_raw', 'time', 
                chunk_time_interval => INTERVAL '1 day',
                if_not_exists => TRUE
            )
        """))
        conn.commit()
    print("Гипертаблица metrics_raw создана")

if __name__ == "__main__":
    init_timescale()