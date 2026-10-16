"""Тесты дашборда на главной: сегодняшние привычки, уровень, дедлайны."""

from datetime import date, timedelta

from sqlmodel import select

from app.models import Goal, User
from tests.conftest import register_user


def test_dashboard_shows_habit_and_level(client):
    register_user(client, login="hank", mail="hank@example.com")
    client.post("/habits", data={"name": "Отжимания"})

    home = client.get("/")
    assert "Отжимания" in home.text
    assert "Новичок" in home.text
    assert "Отметить" in home.text


def test_dashboard_shows_upcoming_deadline(client, session):
    register_user(client, login="iris", mail="iris@example.com")
    client.post("/goals", data={"name": "Мечта"})

    user = session.exec(select(User).where(User.login == "iris")).first()
    dream = session.exec(select(Goal).where(Goal.uid == user.id, Goal.parent_id == None)).first()  # noqa: E711

    deadline = (date.today() + timedelta(days=3)).isoformat()
    client.post(f"/goals/{dream.id}/child", data={"name": "Сдать проект", "deadline": deadline})

    home = client.get("/")
    assert "Сдать проект" in home.text
    assert "Ближайшие дедлайны" in home.text


def test_dashboard_hides_completed_goal_deadline(client, session):
    register_user(client, login="jill", mail="jill@example.com")
    client.post("/goals", data={"name": "Мечта"})
    user = session.exec(select(User).where(User.login == "jill")).first()
    dream = session.exec(select(Goal).where(Goal.uid == user.id, Goal.parent_id == None)).first()  # noqa: E711

    deadline = (date.today() + timedelta(days=1)).isoformat()
    client.post(f"/goals/{dream.id}/child", data={"name": "Готовая цель", "deadline": deadline})
    goal = session.exec(select(Goal).where(Goal.parent_id == dream.id)).first()

    client.post(f"/goals/{goal.id}/complete")
    home = client.get("/")
    assert "Готовая цель" not in home.text


def test_dashboard_shows_daily_tasks(client):
    register_user(client, login="kyle", mail="kyle@example.com")
    home = client.get("/")
    assert "Ежедневное задание" in home.text
    assert "Выполнено" in home.text


def test_dashboard_shows_last_achievement(client):
    register_user(client, login="liu", mail="liu@example.com")
    client.post("/habits", data={"name": "Бег"})  # выдаёт "Первая привычка"

    home = client.get("/")
    assert "Последнее достижение" in home.text
    assert "Первая привычка" in home.text
