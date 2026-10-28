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


# ---------------------------------------------------------------------------
# Сезоны (§4 ТЗ). season_template в БД не хранится — он версионируется в
# app/seasons_library/*.yaml (app/seasons/schema.py — pydantic-схема).
# ---------------------------------------------------------------------------


class Wave(SQLModel, table=True):
    """Волна: общий старт по понедельникам."""

    __tablename__ = "wave"

    id: Optional[int] = Field(default=None, primary_key=True)
    start_date: date = Field(index=True)
    template_id: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=_utcnow)


class Season(SQLModel, table=True):
    """Сезон пользователя — один конкретный проход по шаблону."""

    __tablename__ = "season"

    id: Optional[int] = Field(default=None, primary_key=True)
    uid: int = Field(foreign_key="users.id", index=True)
    template_id: str
    template_version: int
    title: str
    length_days: int
    wave_id: int = Field(foreign_key="wave.id", index=True)
    prologue_start: Optional[date] = None
    start_date: date
    end_date: date
    metric_name: str
    metric_unit: str
    direction: str  # "up" | "down"
    baseline_value: float
    target_value: float
    projected_value: Optional[float] = None
    days_per_week: int
    weekdays_json: str  # JSON-список чисел 1..7 (пн..вс)
    minutes_per_day: int
    status: str = Field(default="prologue")  # prologue | active | finished | abandoned
    result_tier: Optional[str] = None  # clean | passed | completed
    second_chances_left: int
    created_at: datetime = Field(default_factory=_utcnow)


class SeasonDay(SQLModel, table=True):
    """Один день сезона."""

    __tablename__ = "season_day"

    id: Optional[int] = Field(default=None, primary_key=True)
    season_id: int = Field(foreign_key="season.id", index=True)
    day_number: int
    calendar_date: date = Field(index=True)
    kind: str  # train | rest | measure | active_rest
    title: str
    instructions: str
    minimal_version: str
    status: str = Field(default="planned")  # planned|done|minimal|missed|rescued|rest
    done_at: Optional[datetime] = None  # серверное время отметки
    proof_id: Optional[str] = None


class Measurement(SQLModel, table=True):
    """Замер метрики сезона."""

    __tablename__ = "measurement"

    id: Optional[int] = Field(default=None, primary_key=True)
    season_id: int = Field(foreign_key="season.id", index=True)
    day_number: int
    value: float
    measured_at: datetime = Field(default_factory=_utcnow)  # серверное время
    proof_id: Optional[str] = None
    photo_pose: Optional[str] = None  # front | side | none


class Episode(SQLModel, table=True):
    """Серия — итог недели."""

    __tablename__ = "episode"

    id: Optional[int] = Field(default=None, primary_key=True)
    season_id: int = Field(foreign_key="season.id", index=True)
    week_number: int
    title: str
    summary_json: str
    card_image_path: Optional[str] = None
    created_at: datetime = Field(default_factory=_utcnow)


class Reveal(SQLModel, table=True):
    """Финал сезона."""

    __tablename__ = "reveal"

    id: Optional[int] = Field(default=None, primary_key=True)
    season_id: int = Field(foreign_key="season.id", unique=True, index=True)
    tier: str  # clean | passed | completed
    before_value: float
    after_value: float
    card_image_path: Optional[str] = None
    video_path: Optional[str] = None
    shared: bool = Field(default=False)
    created_at: datetime = Field(default_factory=_utcnow)
