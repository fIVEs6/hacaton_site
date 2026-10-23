"""Подключение к БД и простой накатчик SQL-миграций."""
import time
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"


class Base(DeclarativeBase):
    pass


def get_db():
    """Зависимость FastAPI: сессия на время запроса."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations() -> None:
    """Применяет файлы migrations/*.sql по порядку; уже применённые пропускает."""
    # Ждём, пока БД станет доступна (при старте через docker compose)
    for attempt in range(30):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            break
        except OperationalError:
            time.sleep(1)
    else:
        raise RuntimeError("База данных недоступна")

    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY)"))
        # Блокировка, чтобы два процесса не накатывали миграции одновременно
        conn.execute(text("SELECT pg_advisory_xact_lock(4242)"))
        done = {r[0] for r in conn.execute(text("SELECT name FROM schema_migrations"))}
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.name in done:
                continue
            sql = path.read_text(encoding="utf-8")
            # Транзакцией управляем сами, поэтому убираем BEGIN/COMMIT из файла
            sql = "\n".join(l for l in sql.splitlines() if l.strip().upper() not in ("BEGIN;", "COMMIT;"))
            raw = conn.connection.cursor()
            raw.execute(sql)
            conn.execute(text("INSERT INTO schema_migrations (name) VALUES (:n)"), {"n": path.name})
