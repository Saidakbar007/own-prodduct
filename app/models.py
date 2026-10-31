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
    goal_id: Optional[int] = Field(default=None, foreign_key="goal.id", index=True)  # NewLife v8 (§4): goal 1→N season
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
    # NewLife v8 (§4, §7): какую метрику несёт value (weight/run_minutes/reps/
    # steps_avg7d/sleep_hours_avg7d/...), плюс доп. метрики замера одной
    # строкой (обхваты и т.п.) — JSON {"waist": 80.0, "chest": 95.0}.
    metric_key: Optional[str] = None
    extra_metrics_json: Optional[str] = None


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


# ---------------------------------------------------------------------------
# NewLife v8 (NEWLIFE_V8_SPEC.md §4): точка А, сферы, расписание, привычки,
# методы. Сезоны (выше) не меняются по сути — Goal лишь связывает их с целью
# и сферой; вся старая модель данных и данные существующих пользователей
# сохраняются без изменений (только новые таблицы и nullable-поля).
# ---------------------------------------------------------------------------


class Profile(SQLModel, table=True):
    """Точка А: тело, режим дня, ограничения (§4, §5 онбординг)."""

    __tablename__ = "profile"

    id: Optional[int] = Field(default=None, primary_key=True)
    uid: int = Field(foreign_key="users.id", unique=True, index=True)
    height_cm: Optional[int] = None
    weight_kg: Optional[float] = None  # последний известный вес
    wake_time: Optional[str] = None  # "HH:MM"
    sleep_time: Optional[str] = None
    chronotype: Optional[str] = None  # morning | day | evening | varies
    daily_minutes: Optional[int] = None  # 15 | 30 | 60 | 90
    constraints_json: str = Field(default="[]")  # ["no_gym","has_pullup_bar",...]
    main_obstacle: Optional[str] = None  # tired|no_time|forget|phone|quit_after_week
    onboarding_done_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=_utcnow)


class SphereState(SQLModel, table=True):
    """Текущий уровень/приоритет/активность одной из 11 сфер для человека."""

    __tablename__ = "sphere_state"

    id: Optional[int] = Field(default=None, primary_key=True)
    uid: int = Field(foreign_key="users.id", index=True)
    sphere_id: str = Field(index=True)  # body | mind | character | ...
    level: int = Field(default=1)  # 1..10
    priority: int = Field(default=2)  # 1..3
    active: bool = Field(default=False)
    updated_at: datetime = Field(default_factory=_utcnow)


class SphereLevelHistory(SQLModel, table=True):
    """История уровня сферы — для сравнения "с начала" и "с прошлого месяца"
    на колесе жизни (§12)."""

    __tablename__ = "sphere_level_history"

    id: Optional[int] = Field(default=None, primary_key=True)
    uid: int = Field(foreign_key="users.id", index=True)
    sphere_id: str = Field(index=True)
    level: int
    recorded_at: datetime = Field(default_factory=_utcnow, index=True)


class Commitment(SQLModel, table=True):
    """Обязательное дело — неподвижный блок расписания (§4, §6 п.1)."""

    __tablename__ = "commitment"

    id: Optional[int] = Field(default=None, primary_key=True)
    uid: int = Field(foreign_key="users.id", index=True)
    title: str
    category: str  # study|work|commute|family|religion|other
    weekdays_json: str = Field(default="[]")  # [1..7]
    start_time: str  # "HH:MM"
    end_time: str
    active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=_utcnow)


class Task(SQLModel, table=True):
    """Разовое дело — расставляется планировщиком по приоритету Эйзенхауэра
    и дедлайну (§4, §6 п.3)."""

    __tablename__ = "task"

    id: Optional[int] = Field(default=None, primary_key=True)
    uid: int = Field(foreign_key="users.id", index=True)
    title: str
    category: Optional[str] = None
    task_date: date = Field(index=True)
    start_time: Optional[str] = None  # "HH:MM", nullable — планировщик сам найдёт окно
    duration_min: int = Field(default=30)
    priority: str = Field(default="do")  # do|plan|delegate|drop (Эйзенхауэр)
    deadline: Optional[date] = None
    status: str = Field(default="planned")  # planned|done|missed|moved
    created_at: datetime = Field(default_factory=_utcnow)


class Goal(SQLModel, table=True):
    """Цель сферы (§4, §7): связывает сферу и библиотечный шаблон сезона с
    выбранной правильной метрикой. Один Goal может пройти несколько Season
    (1→N) — например уровень за уровнем той же цели."""

    __tablename__ = "goal"

    id: Optional[int] = Field(default=None, primary_key=True)
    uid: int = Field(foreign_key="users.id", index=True)
    sphere_id: str = Field(index=True)
    template_id: str  # id из app/seasons_library/*.yaml
    title: str
    metric_key: str  # §7: weight_body | run_minutes | max_reps | steps_avg7d | sleep_hours_avg7d
    baseline: float
    target: float
    safe_rate: Optional[float] = None  # безопасный темп в неделю (§7/§8)
    projected_date: Optional[date] = None
    status: str = Field(default="active")  # active|finished|abandoned
    created_at: datetime = Field(default_factory=_utcnow)


class Habit(SQLModel, table=True):
    """Полезная привычка (§10): из каталога или своя."""

    __tablename__ = "habit"

    id: Optional[int] = Field(default=None, primary_key=True)
    uid: int = Field(foreign_key="users.id", index=True)
    catalog_id: Optional[str] = None  # id из каталога ~40 привычек, None — своя
    title: str
    spheres_json: str = Field(default="[]")  # список id сфер
    days_json: str = Field(default="[]")  # [1..7]
    time_pref: str = Field(default="exact")  # morning|day|evening|exact
    exact_time: Optional[str] = None  # "HH:MM"
    duration_min: int = Field(default=10)
    minimal_version: str = ""
    anchor_text: Optional[str] = None  # привычка-якорь (§9 Clear/Fogg)
    if_then_text: Optional[str] = None  # намерение "если-то" (§9 Gollwitzer)
    active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=_utcnow)


class HabitLog(SQLModel, table=True):
    __tablename__ = "habit_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    habit_id: int = Field(foreign_key="habit.id", index=True)
    log_date: date = Field(index=True)
    status: str  # done|minimal|missed
    at: datetime = Field(default_factory=_utcnow)  # серверное время отметки


class BadHabit(SQLModel, table=True):
    """Плохая привычка (§10): тренд вниз, не "ноль сразу"."""

    __tablename__ = "bad_habit"

    id: Optional[int] = Field(default=None, primary_key=True)
    uid: int = Field(foreign_key="users.id", index=True)
    catalog_id: Optional[str] = None
    title: str
    triggers_json: str = Field(default="[]")  # id триггеров из каталога
    replacement_id: Optional[str] = None  # id замены из каталога привычек
    baseline_per_day: float
    target_per_day: float
    unit: str = Field(default="times")  # times|minutes
    active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=_utcnow)


class BadHabitLog(SQLModel, table=True):
    """Лог в один тап: "сорвался" + опционально триггер."""

    __tablename__ = "bad_habit_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    bad_habit_id: int = Field(foreign_key="bad_habit.id", index=True)
    log_date: date = Field(index=True)
    value: float  # суммарное значение за день (раз/минут)
    trigger_id: Optional[str] = None
    at: datetime = Field(default_factory=_utcnow)


class Checkin(SQLModel, table=True):
    """Ежедневный чек-ин энергии/стресса/настроения (§11)."""

    __tablename__ = "checkin"

    id: Optional[int] = Field(default=None, primary_key=True)
    uid: int = Field(foreign_key="users.id", index=True)
    checkin_date: date = Field(index=True)
    energy: int  # 1..5
    stress: int  # 1..5
    mood: int  # 1..5
    created_at: datetime = Field(default_factory=_utcnow)


class ScheduleBlock(SQLModel, table=True):
    """Один блок дневного расписания (§6) — результат работы scheduler.py."""

    __tablename__ = "schedule_block"

    id: Optional[int] = Field(default=None, primary_key=True)
    uid: int = Field(foreign_key="users.id", index=True)
    block_date: date = Field(index=True)
    start_time: str  # "HH:MM"
    end_time: str
    kind: str  # fixed|goal_action|habit|task|sleep|buffer
    ref_type: Optional[str] = None  # commitment|season_day|habit|task — None для sleep/buffer
    ref_id: Optional[int] = None
    title: str = ""
    status: str = Field(default="planned")  # planned|done|minimal|missed|moved
    moved_by_user: bool = Field(default=False)
    created_at: datetime = Field(default_factory=_utcnow)


class MethodEvent(SQLModel, table=True):
    """Срабатывание метода саморазвития (§9) — для аналитики и истории."""

    __tablename__ = "method_event"

    id: Optional[int] = Field(default=None, primary_key=True)
    uid: int = Field(foreign_key="users.id", index=True)
    method_id: str = Field(index=True)
    trigger: str
    shown_at: datetime = Field(default_factory=_utcnow)
    accepted: Optional[bool] = None
