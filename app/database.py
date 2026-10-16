"""
Подключение к базе данных SQLite через SQLModel.
"""

from sqlmodel import SQLModel, Session, create_engine

# Файл базы данных лежит в корне проекта
sqlite_url = "sqlite:///app.db"

# check_same_thread=False нужен, т.к. FastAPI может обращаться к базе из разных потоков
engine = create_engine(sqlite_url, echo=False, connect_args={"check_same_thread": False})


def create_db_and_tables():
    """Создаёт все таблицы, описанные в models.py, если их ещё нет."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Отдаёт сессию для работы с базой (используется как зависимость в роутерах)."""
    with Session(engine) as session:
        yield session
