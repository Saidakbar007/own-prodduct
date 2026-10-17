"""Тесты достижений: выдаются ровно один раз при выполнении условия."""

from datetime import timedelta

from sqlmodel import select

from app.models import Habit, HabitHistory, User, UserAchievement
from app.routers.habits import _now
from app.services.achievements import check_and_award_achievements
from tests.conftest import register_user


def test_first_habit_achievement_awarded_on_creation(client, session):
    register_user(client, login="vera", mail="vera@example.com")
    resp = client.post("/habits", data={"name": "Бег", "sphere": "health"})
    assert "Первая привычка" in resp.text or "🌱" in resp.text

    user = session.exec(select(User).where(User.login == "vera")).first()
    earned = session.exec(select(UserAchievement).where(UserAchievement.uid == user.id)).all()
    assert len(earned) == 1


def test_achievement_not_awarded_twice(client, session):
    register_user(client, login="walt", mail="walt@example.com")
    client.post("/habits", data={"name": "Бег", "sphere": "health"})
    client.post("/habits", data={"name": "Плавание", "sphere": "health"})  # вторая привычка — достижение уже есть

    user = session.exec(select(User).where(User.login == "walt")).first()
    earned = session.exec(select(UserAchievement).where(UserAchievement.uid == user.id)).all()
    assert len(earned) == 1  # не дублируется


def test_streak_7_achievement(client, session):
    register_user(client, login="xavier", mail="xavier@example.com")
    client.post("/habits", data={"name": "Йога", "sphere": "health"})

    user = session.exec(select(User).where(User.login == "xavier")).first()
    habit = session.exec(select(Habit).where(Habit.uid == user.id)).first()

    # Напрямую создаём историю за 7 дней подряд (симулируем прошлые отметки)
    for days_ago in range(7):
        session.add(HabitHistory(h_id=habit.id, time=_now() - timedelta(days=days_ago)))
    session.commit()

    new_achievements = check_and_award_achievements(session, user)
    codes = [a.code for a in new_achievements]
    assert "streak_7" in codes
