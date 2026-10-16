"""
Модели базы данных (SQLModel).

Названия таблиц и полей взяты из ER-диаграммы проекта и не меняются,
даже если где-то есть опечатки (например "hight", "familly_stat") —
это сделано специально, чтобы совпадать с диаграммой.
"""

from datetime import date, datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class Registration(SQLModel, table=True):
    """Таблица регистрации: данные, которые пользователь вводит при создании аккаунта."""

    __tablename__ = "registration"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    age: Optional[int] = None
    gender: Optional[str] = None
    mail: str = Field(unique=True, index=True)
    login: str = Field(unique=True, index=True)
    password: str  # хранится только хеш пароля, никогда открытый текст


class User(SQLModel, table=True):
    """Профиль пользователя: данные о здоровье/статусе + счётчики привычек и целей."""

    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    mail: str = Field(unique=True, index=True)
    login: str = Field(unique=True, index=True)
    weight: Optional[float] = None
    hight: Optional[float] = None
    familly_stat: Optional[str] = None
    status: Optional[str] = None
    habits: int = Field(default=0)  # количество привычек, обновляется автоматически
    goals: int = Field(default=0)   # количество целей, обновляется автоматически


class Habit(SQLModel, table=True):
    """Привычка пользователя."""

    __tablename__ = "habits"

    id: Optional[int] = Field(default=None, primary_key=True)
    uid: int = Field(foreign_key="users.id")
    name: str
    description: Optional[str] = None
    time_start: Optional[datetime] = None
    time_end: Optional[datetime] = None
    status: str = Field(default="active")
    point: int = Field(default=0)        # базовые очки за одну отметку (считает сервер по сложности)
    story_point: float = Field(default=1.0)  # множитель сложности привычки
    habit_type: str = Field(default="useful")  # useful (полезная) / harmful (вредная, "день без срыва")
    frequency: str = Field(default="daily")    # daily (каждый день) / weekly (по дням недели)
    weekdays: Optional[str] = None  # для frequency="weekly": дни недели CSV, "0,2,4" (0=понедельник)


class HabitHistory(SQLModel, table=True):
    """История отметок привычки (антиобман: время ставит сервер)."""

    __tablename__ = "habits_history"

    id: Optional[int] = Field(default=None, primary_key=True)
    h_id: int = Field(foreign_key="habits.id")
    time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Goal(SQLModel, table=True):
    """Цель пользователя. Мечта хранится как цель верхнего уровня (parent_id = None)."""

    __tablename__ = "goals"

    id: Optional[int] = Field(default=None, primary_key=True)
    uid: int = Field(foreign_key="users.id")
    name: str
    status: str = Field(default="active")
    time_start: Optional[datetime] = None
    time_end: Optional[datetime] = None
    description: Optional[str] = None
    deadline: Optional[date] = None
    point: int = Field(default=0)
    story_point: float = Field(default=1.0)
    parent_id: Optional[int] = Field(default=None, foreign_key="goals.id")  # мечта = цель без родителя


class GoalHistory(SQLModel, table=True):
    """История прогресса по цели."""

    __tablename__ = "goals_history"

    id: Optional[int] = Field(default=None, primary_key=True)
    h_id: int = Field(foreign_key="goals.id")
    time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GoalStep(SQLModel, table=True):
    """Шаг внутри цели (v2). Прогресс цели = доля выполненных шагов."""

    __tablename__ = "goal_steps"

    id: Optional[int] = Field(default=None, primary_key=True)
    goal_id: int = Field(foreign_key="goals.id")
    name: str
    done: bool = Field(default=False)
    created_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Level(SQLModel, table=True):
    """Уровень пользователя: сумма очков и название текущего уровня."""

    __tablename__ = "level"

    id: Optional[int] = Field(default=None, primary_key=True)
    uid: int = Field(foreign_key="users.id")
    point: int = Field(default=0)
    name: str = Field(default="Новичок")


class Training(SQLModel, table=True):
    """Тренировочная программа, привязанная к цели."""

    __tablename__ = "Training"

    id: Optional[int] = Field(default=None, primary_key=True)
    uid: int = Field(foreign_key="users.id")
    g_id: int = Field(foreign_key="goals.id")
    name: str
    program: Optional[str] = None


class Education(SQLModel, table=True):
    """Образовательная программа, привязанная к цели."""

    __tablename__ = "education"

    id: Optional[int] = Field(default=None, primary_key=True)
    uid: int = Field(foreign_key="users.id")
    g_id: int = Field(foreign_key="goals.id")
    name: str
    program: Optional[str] = None


class Friend(SQLModel, table=True):
    """Связь между друзьями со статусом заявки."""

    __tablename__ = "Friends"

    id: Optional[int] = Field(default=None, primary_key=True)
    uid: int = Field(foreign_key="users.id")
    friend_id: int = Field(foreign_key="users.id")
    status: str = Field(default="pending")  # pending / accepted / declined
    created_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    update_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class Achievement(SQLModel, table=True):
    """Каталог достижений (v2). Заполняется один раз при старте сервера."""

    __tablename__ = "achievements"

    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(unique=True, index=True)
    name: str
    description: str
    icon: str = Field(default="🏆")


class UserAchievement(SQLModel, table=True):
    """Какие достижения получил пользователь и когда (v2)."""

    __tablename__ = "user_achievements"

    id: Optional[int] = Field(default=None, primary_key=True)
    uid: int = Field(foreign_key="users.id")
    achievement_id: int = Field(foreign_key="achievements.id")
    earned_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DailyTask(SQLModel, table=True):
    """Ежедневное мини-задание с бонусными очками (v2)."""

    __tablename__ = "daily_tasks"

    id: Optional[int] = Field(default=None, primary_key=True)
    uid: int = Field(foreign_key="users.id")
    date: date
    description: str
    points: int = Field(default=20)
    done: bool = Field(default=False)


class PointsLog(SQLModel, table=True):
    """
    Журнал начислений очков с отметкой времени (v2).
    Нужен, чтобы считать очки за неделю (рейтинг друзей), а не только общую сумму.
    """

    __tablename__ = "points_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    uid: int = Field(foreign_key="users.id")
    points: int
    time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CoachMessage(SQLModel, table=True):
    """Сообщение в истории переписки с AI-коучем (v2)."""

    __tablename__ = "coach_messages"

    id: Optional[int] = Field(default=None, primary_key=True)
    uid: int = Field(foreign_key="users.id")
    role: str  # "user" или "coach"
    text: str
    time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
