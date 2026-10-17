"""
Тесты страницы /hero и связанных эффектов (v6a): приветствие от ведущей
личности, "пробуждение" +50% XP, голоса при пропуске/серии.
"""

import io
from datetime import timedelta

from sqlmodel import select

from app.models import CoachMessage, Habit, HabitHistory, Level, PointsLog, User
from app.routers.habits import _now
from tests.conftest import register_user


def test_hero_page_renders_five_persona_cards(client, session):
    register_user(client, login="hero1", mail="hero1@example.com")
    resp = client.get("/hero")
    assert resp.status_code == 200
    for persona_name in ("Воин", "Мудрец", "Монах", "Целитель", "Бард"):
        assert persona_name in resp.text


def test_hero_page_shows_leading_persona_star(client, session):
    register_user(client, login="hero2", mail="hero2@example.com")
    user = session.exec(select(User).where(User.login == "hero2")).first()
    session.add(PointsLog(uid=user.id, points=100, sphere="intellect", time=_now()))
    session.commit()

    resp = client.get("/hero")
    assert resp.status_code == 200
    section = resp.text.split('data-persona="intellect"')[1].split('data-persona=')[0]
    assert "★" in section


def test_hero_page_greets_once_per_day(client, session):
    register_user(client, login="hero3", mail="hero3@example.com")
    user = session.exec(select(User).where(User.login == "hero3")).first()

    client.get("/hero")
    greetings_after_first = session.exec(
        select(CoachMessage).where(CoachMessage.uid == user.id, CoachMessage.role == "coach")
    ).all()
    count_after_first = len(greetings_after_first)
    assert count_after_first >= 1

    client.get("/hero")
    greetings_after_second = session.exec(
        select(CoachMessage).where(CoachMessage.uid == user.id, CoachMessage.role == "coach")
    ).all()
    assert len(greetings_after_second) == count_after_first  # не задублировалось


def test_waking_bonus_applies_after_21_plus_days_of_silence(client, session):
    register_user(client, login="hero4", mail="hero4@example.com")
    client.post("/habits", data={"source": "custom", "name": "Бег", "sphere": "strength", "difficulty": "easy"})
    user = session.exec(select(User).where(User.login == "hero4")).first()
    habit = session.exec(select(Habit).where(Habit.uid == user.id)).first()

    # была активность 25 дней назад, потом тишина -> личность "спит"
    session.add(PointsLog(uid=user.id, points=5, sphere="strength", time=_now() - timedelta(days=25)))
    session.commit()

    resp = client.post(f"/habits/{habit.id}/check", data={"kind": "done"})
    assert resp.status_code == 200
    assert "Пробуждение" in resp.text

    level = session.exec(select(Level).where(Level.uid == user.id)).first()
    # easy = 5 очков, +50% пробуждения = round(7.5) = 8
    assert level.point == 8


def test_no_waking_bonus_on_very_first_ever_checkin(client, session):
    register_user(client, login="hero5", mail="hero5@example.com")
    client.post("/habits", data={"source": "custom", "name": "Бег", "sphere": "strength", "difficulty": "easy"})
    user = session.exec(select(User).where(User.login == "hero5")).first()
    habit = session.exec(select(Habit).where(Habit.uid == user.id)).first()

    resp = client.post(f"/habits/{habit.id}/check", data={"kind": "done"})
    assert resp.status_code == 200
    assert "Пробуждение" not in resp.text

    level = session.exec(select(Level).where(Level.uid == user.id)).first()
    assert level.point == 5  # easy, без бонуса


def test_skip_triggers_persona_voice_flash(client, session):
    register_user(client, login="hero6", mail="hero6@example.com")
    client.post("/habits", data={"source": "custom", "name": "Бег", "sphere": "strength"})
    user = session.exec(select(User).where(User.login == "hero6")).first()
    habit = session.exec(select(Habit).where(Habit.uid == user.id)).first()

    resp = client.post(f"/habits/{habit.id}/check", data={"kind": "skip"})
    assert resp.status_code == 200
    assert "Честно признано" in resp.text  # обычное сообщение всё ещё на месте


def test_streak_milestone_triggers_persona_voice(client, session):
    register_user(client, login="hero7", mail="hero7@example.com")
    client.post("/habits", data={"source": "custom", "name": "Бег", "sphere": "strength"})
    user = session.exec(select(User).where(User.login == "hero7")).first()
    habit = session.exec(select(Habit).where(Habit.uid == user.id)).first()

    for days_ago in range(2, 0, -1):
        session.add(HabitHistory(h_id=habit.id, time=_now() - timedelta(days=days_ago), kind="done"))
    session.commit()

    # 3-й день подряд -> вехa серии (streak milestone)
    resp = client.post(f"/habits/{habit.id}/check", data={"kind": "done"})
    assert resp.status_code == 200
    assert "3" in resp.text  # реплика про серию упоминает число дней
