"""Тесты шагов внутри цели и прогресса (цель по шагам, мечта — среднее по целям)."""

from sqlmodel import select

from app.models import Goal, GoalStep, User
from app.services.progress import dream_progress_percent, goal_progress_percent
from tests.conftest import register_user


def test_add_and_toggle_steps_updates_progress(client, session):
    register_user(client, login="sam", mail="sam@example.com")
    client.post("/goals", data={"name": "Мечта"})
    user = session.exec(select(User).where(User.login == "sam")).first()
    dream = session.exec(select(Goal).where(Goal.uid == user.id, Goal.parent_id == None)).first()  # noqa: E711
    client.post(f"/goals/{dream.id}/child", data={"name": "Цель"})
    goal = session.exec(select(Goal).where(Goal.parent_id == dream.id)).first()

    assert goal_progress_percent(session, goal) == 0  # нет шагов

    client.post(f"/goals/{goal.id}/steps", data={"name": "Шаг 1"})
    client.post(f"/goals/{goal.id}/steps", data={"name": "Шаг 2"})
    session.expire_all()
    assert goal_progress_percent(session, goal) == 0  # шаги есть, но не выполнены

    step1 = session.exec(select(GoalStep).where(GoalStep.goal_id == goal.id)).first()
    client.post(f"/goals/{goal.id}/steps/{step1.id}/toggle")
    session.expire_all()
    assert goal_progress_percent(session, goal) == 50  # 1 из 2 шагов


def test_completed_goal_is_always_100_percent(client, session):
    register_user(client, login="tara", mail="tara@example.com")
    client.post("/goals", data={"name": "Мечта"})
    user = session.exec(select(User).where(User.login == "tara")).first()
    dream = session.exec(select(Goal).where(Goal.uid == user.id, Goal.parent_id == None)).first()  # noqa: E711
    client.post(f"/goals/{dream.id}/child", data={"name": "Цель"})
    goal = session.exec(select(Goal).where(Goal.parent_id == dream.id)).first()

    client.post(f"/goals/{goal.id}/complete")
    session.expire_all()
    assert goal_progress_percent(session, goal) == 100


def test_dream_progress_is_average_of_children(client, session):
    register_user(client, login="uma2", mail="uma2@example.com")
    client.post("/goals", data={"name": "Мечта"})
    user = session.exec(select(User).where(User.login == "uma2")).first()
    dream = session.exec(select(Goal).where(Goal.uid == user.id, Goal.parent_id == None)).first()  # noqa: E711

    client.post(f"/goals/{dream.id}/child", data={"name": "Цель A"})
    client.post(f"/goals/{dream.id}/child", data={"name": "Цель B"})
    children = session.exec(select(Goal).where(Goal.parent_id == dream.id)).all()

    # Цель A выполнена полностью (100%), цель B не начата (0%) → среднее 50%
    client.post(f"/goals/{children[0].id}/complete")
    session.expire_all()

    assert dream_progress_percent(session, dream) == 50
