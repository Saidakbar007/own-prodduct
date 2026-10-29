"""
Общие фикстуры для тестов. Все тесты работают против одной временной SQLite
базы (создаётся и мигрируется один раз за сессию) — тесты не должны зависеть
от порядка выполнения, поэтому логины/почты в тестах всегда уникальны
(см. фикстуру `unique`).
"""

import os
import tempfile
import uuid

# DATABASE_URL должен быть выставлен ДО первого импорта app.* — модуль
# app.database создаёт engine один раз при импорте.
_tmp_dir = tempfile.mkdtemp(prefix="sezony-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_tmp_dir, 'test.db')}"
os.environ.setdefault("SECRET_KEY", "test-secret-key")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session  # noqa: E402

from app.database import engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _migrated_app():
    """Запускает lifespan (и миграции Alembic) ровно один раз за тестовую сессию."""
    with TestClient(app):
        yield


@pytest.fixture()
def client():
    """Свежий TestClient на каждый тест — у каждого своя cookie-сессия."""
    return TestClient(app)


@pytest.fixture()
def unique():
    """Короткий уникальный суффикс для логинов/почт, чтобы тесты не конфликтовали."""
    return uuid.uuid4().hex[:8]


@pytest.fixture()
def db_session():
    """Прямой доступ к той же тестовой базе — для раскладки данных "задним
    числом" (например, чтобы довести сезон до финала без ожидания реальных дней)."""
    with Session(engine) as session:
        yield session
