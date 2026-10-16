"""Тесты мечт и целей: создание, прогресс, завершение, очки, недоступность чужих."""

from sqlmodel import select

from app.models import Goal, GoalHistory, Level, User
from tests.conftest import register_user


def test_create_dream_and_goal(client, session):
    register_user(client, login="nina", mail="nina@example.com")
    client.post("/goals", data={"name": "Стать программистом", "description": "Моя большая мечта"})

    user = session.exec(select(User).where(User.login == "nina")).first()
    dream = session.exec(select(Goal).where(Goal.uid == user.id, Goal.parent_id == None)).first()  # noqa: E711
    assert dream is not None
    assert user.goals == 1

    client.post(
        f"/goals/{dream.id}/child",
        data={"name": "Выучить Python", "difficulty": "medium"},
    )
    session.refresh(user)
    assert user.goals == 2

    goal = session.exec(select(Goal).where(Goal.parent_id == dream.id)).first()
    assert goal.name == "Выучить Python"


def test_progress_and_complete_awards_points(client, session):
    register_user(client, login="oleg", mail="oleg@example.com")
    client.post("/goals", data={"name": "Мечта"})
    user = session.exec(select(User).where(User.login == "oleg")).first()
    dream = session.exec(select(Goal).where(Goal.uid == user.id, Goal.parent_id == None)).first()  # noqa: E711

    client.post(f"/goals/{dream.id}/child", data={"name": "Цель", "difficulty": "hard"})  # сложно = 200 очков
    goal = session.exec(select(Goal).where(Goal.parent_id == dream.id)).first()
    assert goal.point == 200  # сервер сам выбрал очки по сложности

    client.post(f"/goals/{goal.id}/progress")
    history = session.exec(select(GoalHistory).where(GoalHistory.h_id == goal.id)).all()
    assert len(history) == 1

    resp = client.post(f"/goals/{goal.id}/complete")
    assert resp.status_code == 200

    session.refresh(goal)
    assert goal.status == "completed"

    level = session.exec(select(Level).where(Level.uid == user.id)).first()
    assert level.point == 200

    # повторное завершение не должно начислять очки повторно
    client.post(f"/goals/{goal.id}/complete")
    session.refresh(level)
    assert level.point == 200


def test_deadline_in_the_past_is_rejected(client, session):
    from datetime import date, timedelta

    register_user(client, login="quinn", mail="quinn@example.com")
    client.post("/goals", data={"name": "Мечта"})
    user = session.exec(select(User).where(User.login == "quinn")).first()
    dream = session.exec(select(Goal).where(Goal.uid == user.id, Goal.parent_id == None)).first()  # noqa: E711

    past_date = (date.today() - timedelta(days=1)).isoformat()
    resp = client.post(f"/goals/{dream.id}/child", data={"name": "Цель", "deadline": past_date})
    assert resp.status_code == 400
    assert "прошлом" in resp.text

    goal = session.exec(select(Goal).where(Goal.parent_id == dream.id)).first()
    assert goal is None  # цель не создана


def test_cannot_access_other_users_goal(client, session):
    register_user(client, login="pavel", mail="pavel@example.com")
    client.post("/goals", data={"name": "Чужая мечта"})
    user = session.exec(select(User).where(User.login == "pavel")).first()
    dream = session.exec(select(Goal).where(Goal.uid == user.id, Goal.parent_id == None)).first()  # noqa: E711
    client.get("/logout")

    register_user(client, login="rita", mail="rita@example.com")
    resp = client.get(f"/goals/{dream.id}")
    assert resp.status_code == 404

    resp2 = client.post(f"/goals/{dream.id}/complete")
    assert resp2.status_code == 404
