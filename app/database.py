"""
Подключение к базе данных через SQLModel.
SQLite по умолчанию (разработка и тесты); PostgreSQL — если задан
DATABASE_URL (Render/Neon отдают схему `postgres://` — нормализуем её под
драйвер psycopg3, который используем для обеих баз одинаково через SQLAlchemy).
"""

import os

from sqlmodel import Session, create_engine


def normalize_database_url(url: str) -> str:
    """Приводит URL к виду, который понимает SQLAlchemy + psycopg3."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://") and "+psycopg" not in url:
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


DATABASE_URL = normalize_database_url(os.getenv("DATABASE_URL", "sqlite:///app.db"))

# check_same_thread нужен только SQLite: FastAPI обращается к базе из разных потоков.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)


def get_session():
    """Отдаёт сессию для работы с базой (используется как зависимость в роутерах)."""
    with Session(engine) as session:
        yield session
