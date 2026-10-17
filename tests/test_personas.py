"""
Тесты 5 личностей героя (v6a): стадия по уровню сферы, состояния
активна/дремлет/спит, ведущая личность, "гармония".
"""

from datetime import timedelta

from sqlmodel import select

from app.models import Habit, PointsLog, User
from app.routers.habits import _now
from app.services.personas import (
    PERSONAS,
    days_since_last_activity,
    has_harmony,
    is_waking,
    leading_persona_sphere,
    persona_profile,
    persona_stage,
    persona_state,
)
from tests.conftest import register_user


def test_persona_stage_brackets():
    assert persona_stage(1) == 1
    assert persona_stage(3) == 1
    assert persona_stage(4) == 2
    assert persona_stage(7) == 2
    assert persona_stage(8) == 3
    assert persona_stage(11) == 3
    assert persona_stage(12) == 4
    assert persona_stage(15) == 4
    assert persona_stage(16) == 5
    assert persona_stage(20) == 5


def test_persona_state_thresholds():
    assert persona_state(None) == "спит"  # никогда не было активности
    assert persona_state(0) == "активна"
    assert persona_state(3) == "активна"
    assert persona_state(4) == "дремлет"
    assert persona_state(20) == "дремлет"
    assert persona_state(21) == "спит"
    assert persona_state(100) == "спит"


def test_five_personas_match_spheres():
    assert set(PERSONAS.keys()) == {"strength", "intellect", "discipline", "health", "charisma"}
    assert PERSONAS["strength"] == "Воин"
    assert PERSONAS["intellect"] == "Мудрец"
    assert PERSONAS["discipline"] == "Монах"
    assert PERSONAS["health"] == "Целитель"
    assert PERSONAS["charisma"] == "Бард"


def test_days_since_last_activity_and_is_waking(client, session):
    register_user(client, login="persona1", mail="persona1@example.com")
    user = session.exec(select(User).where(User.login == "persona1")).first()

    assert days_since_last_activity(session, user.id, "strength") is None
    assert is_waking(session, user.id, "strength") is False  # никогда не было активности — это старт, не пробуждение

    session.add(PointsLog(uid=user.id, points=10, sphere="strength", time=_now()))
    session.commit()

    assert days_since_last_activity(session, user.id, "strength") == 0
    assert is_waking(session, user.id, "strength") is False


def test_is_waking_true_after_21_plus_days(client, session):
    register_user(client, login="persona2", mail="persona2@example.com")
    user = session.exec(select(User).where(User.login == "persona2")).first()

    session.add(PointsLog(uid=user.id, points=10, sphere="charisma", time=_now() - timedelta(days=25)))
    session.commit()

    assert days_since_last_activity(session, user.id, "charisma") == 25
    assert is_waking(session, user.id, "charisma") is True


def test_leading_persona_picks_highest_14_day_xp(client, session):
    register_user(client, login="persona3", mail="persona3@example.com")
    user = session.exec(select(User).where(User.login == "persona3")).first()

    session.add(PointsLog(uid=user.id, points=50, sphere="intellect", time=_now()))
    session.add(PointsLog(uid=user.id, points=10, sphere="strength", time=_now()))
    # старая активность вне окна 14 дней не считается
    session.add(PointsLog(uid=user.id, points=1000, sphere="health", time=_now() - timedelta(days=20)))
    session.commit()

    assert leading_persona_sphere(session, user.id) == "intellect"


def test_leading_persona_tie_break_uses_sphere_order(client, session):
    register_user(client, login="persona4", mail="persona4@example.com")
    user = session.exec(select(User).where(User.login == "persona4")).first()

    # никакой активности ни в одной сфере -> все 0, тай-брейк по порядку SPHERES
    assert leading_persona_sphere(session, user.id) == "strength"


def test_has_harmony_requires_all_five_active_within_week(client, session):
    register_user(client, login="persona5", mail="persona5@example.com")
    user = session.exec(select(User).where(User.login == "persona5")).first()

    assert has_harmony(session, user.id) is False  # вообще нет активности

    for sphere in ("strength", "intellect", "discipline", "health"):
        session.add(PointsLog(uid=user.id, points=10, sphere=sphere, time=_now()))
    session.commit()
    assert has_harmony(session, user.id) is False  # харизма не активна

    session.add(PointsLog(uid=user.id, points=10, sphere="charisma", time=_now() - timedelta(days=6)))
    session.commit()
    assert has_harmony(session, user.id) is True


def test_persona_profile_returns_all_five_with_leading_flag(client, session):
    register_user(client, login="persona6", mail="persona6@example.com")
    user = session.exec(select(User).where(User.login == "persona6")).first()
    session.add(PointsLog(uid=user.id, points=50, sphere="health", time=_now()))
    session.commit()

    profile = persona_profile(session, user.id)
    assert len(profile) == 5
    codes = {p["sphere_code"] for p in profile}
    assert codes == {"strength", "intellect", "discipline", "health", "charisma"}

    leading_flags = [p["is_leading"] for p in profile if p["sphere_code"] == "health"]
    assert leading_flags == [True]
    assert sum(1 for p in profile if p["is_leading"]) == 1
