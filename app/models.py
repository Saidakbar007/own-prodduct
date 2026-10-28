"""
Модели данных (SQLModel). Таблицы создаются и обновляются миграциями Alembic
(app/migrations_runner.py), а не напрямую через SQLModel.metadata.
"""

from datetime import date, datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    """Аккаунт. Продукт 18+ — возраст подтверждается при регистрации (§9 ТЗ)."""

    __tablename__ = "users"  # "user" — зарезервированное слово в PostgreSQL

    id: Optional[int] = Field(default=None, primary_key=True)
    login: str = Field(unique=True, index=True)
    email: str = Field(unique=True, index=True)
    password_hash: str
    name: str
    birth_year: int
    timezone: str = Field(default="UTC")
    timezone_changed_at: Optional[datetime] = None
    language: str = Field(default="ru")
    created_at: datetime = Field(default_factory=_utcnow)
