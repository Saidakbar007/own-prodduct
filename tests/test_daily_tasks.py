"""Тесты ежедневных мини-заданий: генерация, идемпотентность, бонусные очки."""

from sqlmodel import select

from app.models import DailyTask, Level, User
from app.services.daily_tasks import get_or_create_today_tasks
from tests.conftest import register_user


def test_three_tasks_generated_and_stable_within_day(client, session):
    register_user(client, login="yana", mail="yana@example.com")
    user = session.exec(select(User).where(User.login == "yana")).first()

    tasks1 = get_or_create_today_tasks(session, user)
    assert len(tasks1) == 3

    tasks2 = get_or_create_today_tasks(session, user)
    assert [t.id for t in tasks1] == [t.id for t in tasks2]  # повторный вызов не создаёт новые


def test_complete_task_awards_bonus_points(client, session):
    register_user(client, login="zoe", mail="zoe@example.com")
    user = session.exec(select(User).where(User.login == "zoe")).first()
    tasks = get_or_create_today_tasks(session, user)
    task = tasks[0]

    resp = client.post(f"/daily-tasks/{task.id}/complete", follow_redirects=False)
    assert resp.status_code == 303

    level = session.exec(select(Level).where(Level.uid == user.id)).first()
    assert level.point == task.points

    session.refresh(task)
    assert task.done is True

    # повторное выполнение не начисляет очки снова
    client.post(f"/daily-tasks/{task.id}/complete")
    session.refresh(level)
    assert level.point == task.points


def test_cannot_complete_other_users_task(client, session):
    register_user(client, login="aaron", mail="aaron@example.com")
    user = session.exec(select(User).where(User.login == "aaron")).first()
    tasks = get_or_create_today_tasks(session, user)
    client.get("/logout")

    register_user(client, login="bella", mail="bella@example.com")
    client.post(f"/daily-tasks/{tasks[0].id}/complete")

    task = session.exec(select(DailyTask).where(DailyTask.id == tasks[0].id)).first()
    assert task.done is False
