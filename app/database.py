"""
Подключение к базе данных SQLite через SQLModel.
Таблицы создаются и обновляются миграциями Alembic (app/migrations_runner.py),
а не напрямую через SQLModel.metadata.
"""

import os

from sqlmodel import Session, create_engine

# Файл базы данных лежит в корне проекта (можно переопределить через DATABASE_URL,
# например для временной БД при проверке миграции схемы)
sqlite_url = os.getenv("DATABASE_URL", "sqlite:///app.db")

# check_same_thread=False нужен, т.к. FastAPI может обращаться к базе из разных потоков
engine = create_engine(sqlite_url, echo=False, connect_args={"check_same_thread": False})


def get_session():
    """Отдаёт сессию для работы с базой (используется как зависимость в роутерах)."""
    with Session(engine) as session:
        yield session
