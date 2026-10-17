"""
Тесты недельного рейтинга друзей: считается по % выполнения привычек за
неделю и streak, а не по XP — иначе выигрывал бы тот, кто просто набрал
больше очков (например, у кого больше или сложнее привычек).
"""

from datetime import timedelta

from sqlmodel import select

from app.models import Friend, Habit, HabitHistory, User
from app.routers.habits import _now
from app.services.points import award_points
from tests.conftest import register_user


def test_leaderboard_ignores_raw_xp_and_uses_completion_percent(client, session):
    register_user(client, login="carmen", mail="carmen@example.com")
    client.post("/habits", data={"name": "Бег", "sphere": "strength"})
    client.get("/logout")
    register_user(client, login="derek", mail="derek@example.com")
    client.get("/logout")

    carmen = session.exec(select(User).where(User.login == "carmen")).first()
    derek = session.exec(select(User).where(User.login == "derek")).first()
    carmen_habit = session.exec(select(Habit).where(Habit.uid == carmen.id)).first()

    client.post("/login", data={"login": "carmen", "password": "secret123"})
    client.post("/friends/request", data={"login": "derek"})
    client.get("/logout")

    client.post("/login", data={"login": "derek", "password": "secret123"})
    pending = session.exec(select(Friend).where(Friend.status == "pending")).first()
    client.post(f"/friends/{pending.id}/accept")

    # derek набрал больше XP напрямую (без привычек) — но это не должно
    # поднять его в рейтинге выше carmen, которая реально выполняет привычку
    award_points(session, derek, 500)

    for days_ago in range(6, -1, -1):
        session.add(HabitHistory(h_id=carmen_habit.id, time=_now() - timedelta(days=days_ago), kind="done"))
    session.commit()

    page = client.get("/friends")
    leaderboard_section = page.text.split("Рейтинг за неделю")[1]
    assert leaderboard_section.index("carmen") < leaderboard_section.index("derek")
    assert "100%" in leaderboard_section


def test_leaderboard_breaks_ties_by_streak(client, session):
    register_user(client, login="farah", mail="farah@example.com")
    client.post("/habits", data={"name": "Чтение", "sphere": "intellect"})
    client.get("/logout")
    register_user(client, login="greg", mail="greg@example.com")
    client.post("/habits", data={"name": "Йога", "sphere": "health"})
    client.get("/logout")

    farah = session.exec(select(User).where(User.login == "farah")).first()
    greg = session.exec(select(User).where(User.login == "greg")).first()
    farah_habit = session.exec(select(Habit).where(Habit.uid == farah.id)).first()
    greg_habit = session.exec(select(Habit).where(Habit.uid == greg.id)).first()

    client.post("/login", data={"login": "farah", "password": "secret123"})
    client.post("/friends/request", data={"login": "greg"})
    client.get("/logout")

    client.post("/login", data={"login": "greg", "password": "secret123"})
    pending = session.exec(select(Friend).where(Friend.status == "pending")).first()
    client.post(f"/friends/{pending.id}/accept")

    # оба выполняют привычку все 7 дней (100%), но у farah streak длиннее
    for days_ago in range(13, -1, -1):
        session.add(HabitHistory(h_id=farah_habit.id, time=_now() - timedelta(days=days_ago), kind="done"))
    for days_ago in range(6, -1, -1):
        session.add(HabitHistory(h_id=greg_habit.id, time=_now() - timedelta(days=days_ago), kind="done"))
    session.commit()

    page = client.get("/friends")
    leaderboard_section = page.text.split("Рейтинг за неделю")[1]
    assert leaderboard_section.index("farah") < leaderboard_section.index("greg")
