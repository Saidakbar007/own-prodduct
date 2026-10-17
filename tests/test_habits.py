"""
Тесты привычек: создание, отметка, антиобман (1 раз в день, время ставит сервер),
начисление очков, недоступность чужих привычек.
"""

from sqlmodel import select

from app.models import HabitHistory, Level
from tests.conftest import register_user


def create_habit(client, name="Бег", difficulty="medium", sphere="strength"):
    return client.post("/habits", data={"name": name, "difficulty": difficulty, "sphere": sphere})


def test_create_habit_increments_counter(client):
    register_user(client, login="hugo", mail="hugo@example.com")
    resp = create_habit(client)
    assert resp.status_code == 200
    assert "Бег" in resp.text


def test_check_habit_once_succeeds_and_awards_points(client, session):
    register_user(client, login="ivy", mail="ivy@example.com")
    create_habit(client, name="Марафон", difficulty="hard")  # сложно = 20 очков

    history_before = session.exec(select(HabitHistory)).all()  # пока пусто, привычка ещё не отмечена
    assert history_before == []

    from app.models import Habit, User

    user = session.exec(select(User).where(User.login == "ivy")).first()
    habit = session.exec(select(Habit).where(Habit.uid == user.id)).first()
    assert habit.point == 20  # сервер сам выбрал очки по сложности, клиент их не присылал

    resp = client.post(f"/habits/{habit.id}/check")
    assert resp.status_code == 200
    assert "Сделано" in resp.text

    level = session.exec(select(Level).where(Level.uid == user.id)).first()
    assert level.point == 20


def test_check_habit_twice_same_day_fails(client, session):
    register_user(client, login="jack", mail="jack@example.com")
    create_habit(client)

    from app.models import Habit, User

    user = session.exec(select(User).where(User.login == "jack")).first()
    habit = session.exec(select(Habit).where(Habit.uid == user.id)).first()

    first = client.post(f"/habits/{habit.id}/check")
    assert first.status_code == 200

    second = client.post(f"/habits/{habit.id}/check")
    assert second.status_code == 400
    assert "уже отметили сегодня" in second.text

    history = session.exec(select(HabitHistory).where(HabitHistory.h_id == habit.id)).all()
    assert len(history) == 1


def test_server_sets_check_time_ignoring_client_input(client, session):
    """Клиент пытается подсунуть свою дату — сервер должен игнорировать это и поставить текущее время."""
    register_user(client, login="kate", mail="kate@example.com")
    create_habit(client)

    from datetime import datetime, timezone

    from app.models import Habit, User

    user = session.exec(select(User).where(User.login == "kate")).first()
    habit = session.exec(select(Habit).where(Habit.uid == user.id)).first()

    client.post(
        f"/habits/{habit.id}/check",
        data={"time": "2000-01-01T00:00:00", "date": "2000-01-01"},
    )

    history = session.exec(select(HabitHistory).where(HabitHistory.h_id == habit.id)).first()
    assert history.time.date() == datetime.now(timezone.utc).date()


def test_cannot_check_other_users_habit(client, session):
    register_user(client, login="liam", mail="liam@example.com")
    create_habit(client)
    client.get("/logout")

    from app.models import Habit, User

    liam = session.exec(select(User).where(User.login == "liam")).first()
    liam_habit = session.exec(select(Habit).where(Habit.uid == liam.id)).first()

    register_user(client, login="mia", mail="mia@example.com")
    resp = client.post(f"/habits/{liam_habit.id}/check")
    assert resp.status_code == 404

    history = session.exec(select(HabitHistory).where(HabitHistory.h_id == liam_habit.id)).all()
    assert history == []
