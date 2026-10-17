"""
Тесты часового пояса (v5, пункт 6): задаётся при регистрации, меняется
не чаще раза в 30 дней, "сегодня" для отметок считается по серверному
времени в поясе пользователя.
"""

from datetime import date, datetime, timedelta, timezone

from sqlmodel import select

from app.models import Habit, HabitHistory, User
from app.routers.habits import habit_due_today, habit_logged_today
from app.services.usertime import can_change_timezone, is_valid_timezone, local_date, now_for, today_for
from tests.conftest import register_user


def test_registration_stores_submitted_timezone(client, session):
    client.post(
        "/register",
        data={
            "name": "Тест", "age": 20, "gender": "male",
            "mail": "tz1@example.com", "login": "tzuser1",
            "password": "secret123", "password_confirm": "secret123",
            "timezone": "Asia/Tashkent",
        },
        follow_redirects=False,
    )
    user = session.exec(select(User).where(User.login == "tzuser1")).first()
    assert user.timezone == "Asia/Tashkent"
    assert user.timezone_changed_at is None  # регистрация не считается "сменой"


def test_registration_falls_back_to_utc_for_invalid_timezone(client, session):
    client.post(
        "/register",
        data={
            "name": "Тест", "age": 20, "gender": "male",
            "mail": "tz2@example.com", "login": "tzuser2",
            "password": "secret123", "password_confirm": "secret123",
            "timezone": "Not/A_Real_Zone",
        },
        follow_redirects=False,
    )
    user = session.exec(select(User).where(User.login == "tzuser2")).first()
    assert user.timezone == "UTC"


def test_registration_without_timezone_field_defaults_to_utc(client, session):
    register_user(client, login="tzuser3", mail="tz3@example.com")
    user = session.exec(select(User).where(User.login == "tzuser3")).first()
    assert user.timezone == "UTC"


def test_is_valid_timezone_rejects_garbage():
    assert is_valid_timezone("Europe/Moscow") is True
    assert is_valid_timezone("Not/A_Zone") is False
    assert is_valid_timezone("") is False


def test_profile_timezone_change_updates_and_sets_cooldown(client, session):
    register_user(client, login="tzuser4", mail="tz4@example.com")
    resp = client.post("/profile/timezone", data={"timezone": "America/New_York"})
    assert resp.status_code == 200

    user = session.exec(select(User).where(User.login == "tzuser4")).first()
    assert user.timezone == "America/New_York"
    assert user.timezone_changed_at is not None
    assert can_change_timezone(user) is False


def test_profile_timezone_change_blocked_within_30_days(client, session):
    register_user(client, login="tzuser5", mail="tz5@example.com")
    client.post("/profile/timezone", data={"timezone": "America/New_York"})

    resp = client.post("/profile/timezone", data={"timezone": "Europe/Paris"})
    assert resp.status_code == 400

    user = session.exec(select(User).where(User.login == "tzuser5")).first()
    assert user.timezone == "America/New_York"  # не изменился


def test_profile_timezone_change_allowed_after_30_days(client, session):
    register_user(client, login="tzuser6", mail="tz6@example.com")
    client.post("/profile/timezone", data={"timezone": "America/New_York"})

    user = session.exec(select(User).where(User.login == "tzuser6")).first()
    user.timezone_changed_at = datetime.now(timezone.utc) - timedelta(days=31)
    session.add(user)
    session.commit()

    resp = client.post("/profile/timezone", data={"timezone": "Europe/Paris"})
    assert resp.status_code == 200

    session.refresh(user)
    assert user.timezone == "Europe/Paris"


def test_profile_timezone_change_rejects_invalid_zone(client, session):
    register_user(client, login="tzuser7", mail="tz7@example.com")
    resp = client.post("/profile/timezone", data={"timezone": "Not/A_Zone"})
    assert resp.status_code == 400

    user = session.exec(select(User).where(User.login == "tzuser7")).first()
    assert user.timezone == "UTC"  # не изменился


def test_today_boundary_follows_user_timezone_not_utc(client, session):
    """
    05:00 UTC — это 15 марта по UTC, но ещё 14 марта на Гавайях (UTC-10).
    local_date() должен вернуть именно поясную дату, а не дату момента по UTC.
    """
    register_user(client, login="tzuser8", mail="tz8@example.com")
    user = session.exec(select(User).where(User.login == "tzuser8")).first()
    user.timezone = "Pacific/Honolulu"  # UTC-10, без перехода на летнее время
    session.add(user)
    session.commit()

    moment = datetime(2026, 3, 15, 5, 0, tzinfo=timezone.utc)
    assert moment.date() == date(2026, 3, 15)
    assert local_date(user, moment) == date(2026, 3, 14)


def test_habit_due_today_uses_user_local_weekday(client, session):
    register_user(client, login="tzuser9", mail="tz9@example.com")
    user = session.exec(select(User).where(User.login == "tzuser9")).first()

    local_weekday = str(today_for(user).weekday())
    other_weekday = str((today_for(user).weekday() + 3) % 7)

    due_habit = Habit(uid=user.id, name="По плану", point=10, frequency="weekly", weekdays=local_weekday, sphere="strength")
    not_due_habit = Habit(uid=user.id, name="Не сегодня", point=10, frequency="weekly", weekdays=other_weekday, sphere="strength")
    session.add(due_habit)
    session.add(not_due_habit)
    session.commit()

    assert habit_due_today(due_habit, user) is True
    assert habit_due_today(not_due_habit, user) is False


def test_habit_logged_today_respects_user_timezone(client, session):
    register_user(client, login="tzuser10", mail="tz10@example.com")
    user = session.exec(select(User).where(User.login == "tzuser10")).first()
    client.post("/habits", data={"name": "Бег", "sphere": "strength"})
    habit = session.exec(select(Habit).where(Habit.uid == user.id)).first()

    assert habit_logged_today(session, habit.id, user) is False

    session.add(HabitHistory(h_id=habit.id, time=now_for(user), kind="done"))
    session.commit()

    assert habit_logged_today(session, habit.id, user) is True
