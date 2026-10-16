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
        data={"name": "Выучить Python", "point": 100, "story_point": 1.0},
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

    client.post(f"/goals/{dream.id}/child", data={"name": "Цель", "point": 100, "story_point": 1.5})
    goal = session.exec(select(Goal).where(Goal.parent_id == dream.id)).first()

    client.post(f"/goals/{goal.id}/progress")
    history = session.exec(select(GoalHistory).where(GoalHistory.h_id == goal.id)).all()
    assert len(history) == 1

    resp = client.post(f"/goals/{goal.id}/complete")
    assert resp.status_code == 200

    session.refresh(goal)
    assert goal.status == "completed"

    level = session.exec(select(Level).where(Level.uid == user.id)).first()
    assert level.point == 150  # 100 * 1.5

    # повторное завершение не должно начислять очки повторно
    client.post(f"/goals/{goal.id}/complete")
    session.refresh(level)
    assert level.point == 150


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
