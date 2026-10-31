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
    height_cm: Optional[int] = None  # для ИМТ (fat_loss_safe) — собирается в онбординге
    timezone: str = Field(default="UTC")
    timezone_changed_at: Optional[datetime] = None
    language: str = Field(default="ru")
    trust_score: int = Field(default=100)  # честность (§9) — анти-сговор, подозрительные паттерны
    telegram_user_id: Optional[int] = Field(default=None, unique=True, index=True)
    reminder_time: Optional[str] = None  # "HH:MM" по часовому поясу пользователя — напоминания бота
    created_at: datetime = Field(default_factory=_utcnow)


# ---------------------------------------------------------------------------
# Сезоны (§4 ТЗ). season_template в БД не хранится — он версионируется в
# app/seasons_library/*.yaml (app/seasons/schema.py — pydantic-схема).
# ---------------------------------------------------------------------------


class Wave(SQLModel, table=True):
    """Волна: метка недели (понедельник), по которой людей группируют в
    команду. С UX-правки сезон не ждёт понедельника — start_date здесь не
    момент старта, а бакет для группировки (см. DECISIONS.md)."""

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
    status: str = Field(default="active")  # active | finished | abandoned
    result_tier: Optional[str] = None  # clean | passed | completed
    second_chances_left: int
    current_phase: int = Field(default=1)
    # Вторая метрика (пока только muscle_gain: вес тела рядом с рабочим весом,
    # §7 задачи Фазы 2) — nullable, большинство сезонов её не используют.
    secondary_metric_name: Optional[str] = None
    secondary_metric_unit: Optional[str] = None
    secondary_direction: Optional[str] = None  # "up" | "down"
    secondary_baseline_value: Optional[float] = None
    secondary_target_value: Optional[float] = None
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
    proof_id: Optional[int] = Field(default=None, foreign_key="proof.id")
    reminder_sent: bool = Field(default=False)  # §12: без дублей напоминаний бота


class Measurement(SQLModel, table=True):
    """Замер метрики сезона."""

    __tablename__ = "measurement"

    id: Optional[int] = Field(default=None, primary_key=True)
    season_id: int = Field(foreign_key="season.id", index=True)
    day_number: int
    value: float
    secondary_value: Optional[float] = None  # вторая метрика (см. Season)
    measured_at: datetime = Field(default_factory=_utcnow)  # серверное время
    proof_id: Optional[int] = Field(default=None, foreign_key="proof.id")
    photo_pose: Optional[str] = None  # front | side | none


class Proof(SQLModel, table=True):
    """Фото-доказательство (§9): приватное по умолчанию, непредсказуемое имя файла."""

    __tablename__ = "proof"

    id: Optional[int] = Field(default=None, primary_key=True)
    uid: int = Field(foreign_key="users.id", index=True)
    filename: str  # непредсказуемое имя в uploads/, не выдаём по порядковому id
    content_type: str
    phash: Optional[str] = None  # перцептивный хэш — поиск повторно используемых фото
    is_blurry: bool = Field(default=False)
    is_blank: bool = Field(default=False)
    created_at: datetime = Field(default_factory=_utcnow)


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


# ---------------------------------------------------------------------------
# Люди (§4, §7 п.6-7 ТЗ) — Фаза 3.
# ---------------------------------------------------------------------------


class Squad(SQLModel, table=True):
    """Состав: до 8 человек волны с похожей целью (один шаблон)."""

    __tablename__ = "squad"

    id: Optional[int] = Field(default=None, primary_key=True)
    wave_id: int = Field(foreign_key="wave.id", index=True)
    template_id: str
    created_at: datetime = Field(default_factory=_utcnow)


class SquadMember(SQLModel, table=True):
    """Членство в составе. Анонимно по умолчанию, выход — в один клик."""

    __tablename__ = "squad_member"

    id: Optional[int] = Field(default=None, primary_key=True)
    squad_id: int = Field(foreign_key="squad.id", index=True)
    uid: int = Field(foreign_key="users.id", index=True)
    season_id: int = Field(foreign_key="season.id", index=True)
    anonymous: bool = Field(default=True)
    joined_at: datetime = Field(default_factory=_utcnow)
    left_at: Optional[datetime] = None


class SquadReaction(SQLModel, table=True):
    """Реакция-"огонёк" на отметку участника состава (без личных сообщений)."""

    __tablename__ = "squad_reaction"

    id: Optional[int] = Field(default=None, primary_key=True)
    squad_id: int = Field(foreign_key="squad.id", index=True)
    from_uid: int = Field(foreign_key="users.id", index=True)
    to_uid: int = Field(foreign_key="users.id", index=True)
    reacted_on: date  # день, к которому относится реакция
    emoji: str = Field(default="🔥")
    created_at: datetime = Field(default_factory=_utcnow)


class Challenge(SQLModel, table=True):
    """Вызов "Спорим?" (§7 п.7): дуэль двух сезонов по одному шаблону."""

    __tablename__ = "challenge"

    id: Optional[int] = Field(default=None, primary_key=True)
    from_uid: int = Field(foreign_key="users.id", index=True)
    to_uid: Optional[int] = Field(default=None, foreign_key="users.id", index=True)
    invite_code: str = Field(unique=True, index=True)
    season_id_from: int = Field(foreign_key="season.id")
    season_id_to: Optional[int] = Field(default=None, foreign_key="season.id")
    terms_text: str
    status: str = Field(default="pending")  # pending|active|finished|declined
    winner_uid: Optional[int] = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=_utcnow)


class ChallengeDispute(SQLModel, table=True):
    """«Сомневаюсь» (§7 п.7): соперник оспаривает отметку дня внутри вызова —
    не трогает честность самого сезона, только зачёт в этом конкретном вызове."""

    __tablename__ = "challenge_dispute"

    id: Optional[int] = Field(default=None, primary_key=True)
    challenge_id: int = Field(foreign_key="challenge.id", index=True)
    day_number: int
    uid: int = Field(foreign_key="users.id")  # чья отметка оспаривается
    disputed_by: int = Field(foreign_key="users.id")
    status: str = Field(default="pending")  # pending|confirmed|expired
    created_at: datetime = Field(default_factory=_utcnow)
    confirmed_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Своя цель и метрики (§5, §13, §14 ТЗ) — Фаза 4.
# ---------------------------------------------------------------------------


class CustomTemplateDraft(SQLModel, table=True):
    """ИИ-сгенерированный шаблон "своей цели" (§5): кэш по тексту цели,
    админ может утвердить (approved=True) — тогда он доступен как обычный
    библиотечный шаблон наравне с пятью стартовыми."""

    __tablename__ = "custom_template_draft"

    id: Optional[int] = Field(default=None, primary_key=True)
    goal_text: str
    goal_text_hash: str = Field(unique=True, index=True)
    template_id: str = Field(unique=True, index=True)
    template_yaml: str
    approved: bool = Field(default=False)
    created_at: datetime = Field(default_factory=_utcnow)


class Event(SQLModel, table=True):
    """Событие метрик (§13): воронка онбординга, удержание, вирусность."""

    __tablename__ = "event"

    id: Optional[int] = Field(default=None, primary_key=True)
    event_type: str = Field(index=True)
    uid: Optional[int] = Field(default=None, foreign_key="users.id", index=True)
    season_id: Optional[int] = Field(default=None, foreign_key="season.id")
    meta_json: Optional[str] = None
    created_at: datetime = Field(default_factory=_utcnow, index=True)
