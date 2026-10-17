"""Тесты данных для графиков и карточек статистики."""

from sqlmodel import select

from app.models import User
from app.services.points import award_points
from app.services.stats import checks_per_day, points_per_week, stats_cards
from tests.conftest import register_user


def test_checks_per_day_counts_todays_check(client, session):
    register_user(client, login="emil", mail="emil@example.com")
    client.post("/habits", data={"name": "Бег", "sphere": "health"})

    from app.models import Habit

    user = session.exec(select(User).where(User.login == "emil")).first()
    habit = session.exec(select(Habit).where(Habit.uid == user.id)).first()
    client.post(f"/habits/{habit.id}/check")

    data = checks_per_day(session, user.id, days=30)
    assert len(data) == 30
    assert data[-1]["count"] == 1  # последний элемент — сегодня


def test_points_per_week_reflects_awarded_points(client, session):
    register_user(client, login="farid", mail="farid@example.com")
    user = session.exec(select(User).where(User.login == "farid")).first()
    award_points(session, user, 50)

    data = points_per_week(session, user.id, weeks=8)
    assert data[-1]["points"] == 50  # текущая неделя — последний элемент


def test_stats_cards_reflect_activity(client, session):
    register_user(client, login="gwen", mail="gwen@example.com")
    client.post("/habits", data={"name": "Бег", "sphere": "health"})

    from app.models import Habit

    user = session.exec(select(User).where(User.login == "gwen")).first()
    habit = session.exec(select(Habit).where(Habit.uid == user.id)).first()
    client.post(f"/habits/{habit.id}/check")

    cards = stats_cards(session, user.id)
    assert cards["best_streak"] == 1
    assert cards["total_checks"] == 1
    assert cards["goals_completed"] == 0
