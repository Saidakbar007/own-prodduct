"""
Общие фикстуры для тестов: тестовая БД в памяти + тестовый клиент FastAPI.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.database import get_session
from app.main import app
from app.services.achievements import ensure_achievements_seeded
from app.services.seasons import ensure_season_seeded
from app.services.shop import ensure_shop_seeded


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        ensure_achievements_seeded(session)
        ensure_shop_seeded(session)
        ensure_season_seeded(session)
        yield session


@pytest.fixture(name="client")
def client_fixture(session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def register_user(client, login="user1", mail="user1@example.com", password="secret123"):
    """Вспомогательная функция: регистрирует пользователя и возвращает клиент с активной сессией."""
    return client.post(
        "/register",
        data={
            "name": "Тест",
            "age": 20,
            "gender": "male",
            "mail": mail,
            "login": login,
            "password": password,
            "password_confirm": password,
        },
        follow_redirects=False,
    )
