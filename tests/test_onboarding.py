"""Тесты онбординга: 4 шага, создание мечты/привычки, пропуск в любой момент."""

from sqlmodel import select

from app.models import Goal, Habit, User
from tests.conftest import register_user


def test_onboarding_steps_create_dream_and_habit(client, session):
    register_user(client, login="mia2", mail="mia2@example.com")

    step1 = client.get("/onboarding")
    assert step1.status_code == 200

    resp = client.post("/onboarding/dream", data={"name": "Стать здоровым", "sphere": "health"}, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/onboarding/habit"

    resp2 = client.post("/onboarding/habit", data={"name": "Пить воду", "sphere": "health"}, follow_redirects=False)
    assert resp2.status_code == 303
    assert resp2.headers["location"] == "/onboarding/done"

    done_page = client.get("/onboarding/done")
    assert done_page.status_code == 200

    user = session.exec(select(User).where(User.login == "mia2")).first()
    dream = session.exec(select(Goal).where(Goal.uid == user.id)).first()
    habit = session.exec(select(Habit).where(Habit.uid == user.id)).first()
    assert dream.name == "Стать здоровым"
    assert habit.name == "Пить воду"


def test_onboarding_skip_does_not_create_anything(client, session):
    register_user(client, login="nick2", mail="nick2@example.com")
    client.get("/onboarding")  # посмотрел шаг 1, но сразу ушёл на главную

    user = session.exec(select(User).where(User.login == "nick2")).first()
    assert user.goals == 0
    assert user.habits == 0


def test_onboarding_empty_submit_does_not_create_dream(client, session):
    register_user(client, login="oleg2", mail="oleg2@example.com")
    client.post("/onboarding/dream", data={"name": "", "sphere": "health"})

    user = session.exec(select(User).where(User.login == "oleg2")).first()
    assert user.goals == 0
