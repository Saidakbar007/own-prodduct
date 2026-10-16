"""Тесты типа привычки (полезная/вредная), частоты и календаря за 30 дней."""

from sqlmodel import select

from app.models import Habit, User
from tests.conftest import register_user


def test_create_harmful_habit_with_weekly_frequency(client, session):
    register_user(client, login="noah", mail="noah@example.com")
    client.post(
        "/habits",
        data={
            "name": "Не курить",
            "habit_type": "harmful",
            "frequency": "weekly",
            "weekdays": ["0", "2", "4"],
            "difficulty": "hard",
        },
    )

    user = session.exec(select(User).where(User.login == "noah")).first()
    habit = session.exec(select(Habit).where(Habit.uid == user.id)).first()

    assert habit.habit_type == "harmful"
    assert habit.frequency == "weekly"
    assert habit.weekdays == "0,2,4"
    assert habit.point == 20


def test_habit_detail_page_shows_calendar(client, session):
    register_user(client, login="olga", mail="olga@example.com")
    client.post("/habits", data={"name": "Чтение"})

    user = session.exec(select(User).where(User.login == "olga")).first()
    habit = session.exec(select(Habit).where(Habit.uid == user.id)).first()

    resp = client.get(f"/habits/{habit.id}")
    assert resp.status_code == 200
    assert "Последние 30 дней" in resp.text

    client.post(f"/habits/{habit.id}/check")
    resp2 = client.get(f"/habits/{habit.id}")
    assert "bg-green-500" in resp2.text  # сегодняшний день закрашен


def test_cannot_view_other_users_habit_detail(client, session):
    register_user(client, login="pete", mail="pete@example.com")
    client.post("/habits", data={"name": "Бег"})
    user = session.exec(select(User).where(User.login == "pete")).first()
    habit = session.exec(select(Habit).where(Habit.uid == user.id)).first()
    client.get("/logout")

    register_user(client, login="rosa", mail="rosa@example.com")
    resp = client.get(f"/habits/{habit.id}")
    assert resp.status_code == 404
