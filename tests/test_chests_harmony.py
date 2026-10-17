"""Тест: "гармония" поднимает награду сундука на ступень выше (v6a)."""

from datetime import date, datetime, timedelta, timezone

from sqlmodel import select

from app.models import Chest, Habit, HabitHistory, PointsLog, User
from app.services.chests import maybe_award_chest
from tests.conftest import register_user


def _make_full_week_habit(session, user) -> Habit:
    habit = Habit(uid=user.id, name="Бег", point=10, story_point=1.0, sphere="strength")
    session.add(habit)
    session.commit()
    session.refresh(habit)

    monday = date(2026, 1, 12)
    sunday = monday + timedelta(days=6)
    for i in range(7):
        day = monday + timedelta(days=i)
        session.add(
            HabitHistory(
                h_id=habit.id,
                time=datetime(day.year, day.month, day.day, 12, tzinfo=timezone.utc),
                kind="done",
            )
        )
    session.commit()
    return habit, sunday


def test_chest_reward_upgraded_one_tier_with_harmony(client, session, monkeypatch):
    import app.services.chests as chests_module

    register_user(client, login="harmony1", mail="harmony1@example.com")
    user = session.exec(select(User).where(User.login == "harmony1")).first()
    habit, sunday = _make_full_week_habit(session, user)

    class FakeDate(date):
        @classmethod
        def today(cls):
            return sunday

    monkeypatch.setattr(chests_module, "date", FakeDate)
    monkeypatch.setattr(chests_module.random, "choice", lambda options: options[0])

    # без гармонии: первый вариант в списке ["points","points","freeze","badge"][0] = "points"
    # выставим гармонию заранее (все 5 сфер активны за 7 дней) -> badge/freeze/points поднимаются на ступень
    for sphere in ("strength", "intellect", "discipline", "health", "charisma"):
        session.add(PointsLog(uid=user.id, points=1, sphere=sphere, time=datetime.now(timezone.utc)))
    session.commit()

    # принудительно делаем первый выбор "badge", чтобы проверить подъём badge -> freeze
    monkeypatch.setattr(chests_module.random, "choice", lambda options: options[-1] if len(options) == 4 else options[0])

    chest = maybe_award_chest(session, user, habit)
    assert chest is not None
    assert chest.reward_type == "freeze"  # badge поднят на ступень выше гармонией


def test_chest_points_tier_bumped_up_with_harmony(client, session, monkeypatch):
    import app.services.chests as chests_module

    register_user(client, login="harmony2", mail="harmony2@example.com")
    user = session.exec(select(User).where(User.login == "harmony2")).first()
    habit, sunday = _make_full_week_habit(session, user)

    class FakeDate(date):
        @classmethod
        def today(cls):
            return sunday

    monkeypatch.setattr(chests_module, "date", FakeDate)
    monkeypatch.setattr(chests_module.random, "choice", lambda options: options[0] if len(options) == 4 else 20)

    for sphere in ("strength", "intellect", "discipline", "health", "charisma"):
        session.add(PointsLog(uid=user.id, points=1, sphere=sphere, time=datetime.now(timezone.utc)))
    session.commit()

    chest = maybe_award_chest(session, user, habit)
    assert chest is not None
    assert chest.reward_type == "points"
    assert chest.reward_value == "30"  # 20 поднят до следующего тира (30) гармонией


def test_chest_reward_not_upgraded_without_harmony(client, session, monkeypatch):
    import app.services.chests as chests_module

    register_user(client, login="harmony3", mail="harmony3@example.com")
    user = session.exec(select(User).where(User.login == "harmony3")).first()
    habit, sunday = _make_full_week_habit(session, user)

    class FakeDate(date):
        @classmethod
        def today(cls):
            return sunday

    monkeypatch.setattr(chests_module, "date", FakeDate)
    monkeypatch.setattr(chests_module.random, "choice", lambda options: options[-1] if len(options) == 4 else 20)

    chest = maybe_award_chest(session, user, habit)
    assert chest is not None
    assert chest.reward_type == "badge"  # без гармонии — без повышения
