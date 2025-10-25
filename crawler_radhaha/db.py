# db.py
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Render의 DATABASE_URL 환경변수 (없으면 SQLite로 fallback)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///cafeteria.db")

# Render는 postgres:// 로 시작하는 경우가 있으니 변환 필요
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://")

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, future=True)

def _is_sqlite():
    return engine.url.get_backend_name().startswith("sqlite")

def init_db():
    if _is_sqlite():
        schema = """
        CREATE TABLE IF NOT EXISTS lilac_menu(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          day_text TEXT NOT NULL,
          menu TEXT NOT NULL,
          UNIQUE(day_text, menu)
        );
        """
    else:
        schema = """
        CREATE TABLE IF NOT EXISTS lilac_menu(
          id SERIAL PRIMARY KEY,
          day_text TEXT NOT NULL,
          menu TEXT NOT NULL,
          CONSTRAINT uniq_day_menu UNIQUE(day_text, menu)
        );
        """
    with engine.begin() as conn:
        conn.execute(text(schema))

def upsert(items):
    if not items:
        return 0
    if _is_sqlite():
        query = text("""
            INSERT OR IGNORE INTO lilac_menu(day_text, menu)
            VALUES (:d, :m)
        """)
    else:
        query = text("""
            INSERT INTO lilac_menu(day_text, menu)
            VALUES (:d, :m)
            ON CONFLICT (day_text, menu) DO NOTHING
        """)
    added = 0
    with engine.begin() as conn:
        for day, menu in items:
            conn.execute(query, {"d": day, "m": menu})
            added += 1
    return added
