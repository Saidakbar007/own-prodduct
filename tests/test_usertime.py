"""Часовой пояс и серверное "сегодня" (app/services/usertime.py)."""

from datetime import date, datetime, timedelta, timezone

import pytest

from app.models import User
from app.services.usertime import (
    DEFAULT_TIMEZONE,
    can_change_timezone,
    is_valid_timezone,
    local_date,
    now_for,
    today_for,
)


def _user(tz: str = "UTC", timezone_changed_at=None) -> User:
    return User(
        login="x",
        email="x@example.com",
        password_hash="x",
        name="x",
        birth_year=2000,
        timezone=tz,
        timezone_changed_at=timezone_changed_at,
    )


@pytest.mark.parametrize(
    "tz_name,expected",
    [
        ("UTC", True),
        ("Europe/Moscow", True),
        ("Asia/Tashkent", True),
        ("Not/AZone", False),
        ("", False),
    ],
)
def test_is_valid_timezone(tz_name, expected):
    assert is_valid_timezone(tz_name) is expected


def test_now_for_uses_server_time_not_client_time():
    user = _user("Asia/Tashkent")  # UTC+5, без переходов на летнее время
    now = now_for(user)
    utc_now = datetime.now(timezone.utc)
    assert abs((now.utcoffset() or timedelta(0)) - timedelta(hours=5)) < timedelta(minutes=1)
    # Это один и тот же момент времени, просто в другом поясе
    assert abs((now - utc_now).total_seconds()) < 1


def test_today_for_falls_back_to_default_on_invalid_timezone():
    user = _user("Not/AZone")
    # не должно падать — тихо используется DEFAULT_TIMEZONE вместо исключения
    today = today_for(user)
    utc_today = datetime.now(timezone.utc).date()
    assert today in (utc_today - timedelta(days=1), utc_today, utc_today + timedelta(days=1))
    assert is_valid_timezone(DEFAULT_TIMEZONE)


def test_local_date_converts_naive_and_aware_moments():
    user = _user("UTC")
    naive = datetime(2026, 1, 1, 23, 30)
    aware = datetime(2026, 1, 1, 23, 30, tzinfo=timezone.utc)
    assert local_date(user, naive) == local_date(user, aware) == date(2026, 1, 1)


def test_can_change_timezone_without_prior_change():
    user = _user("UTC", timezone_changed_at=None)
    assert can_change_timezone(user) is True


def test_can_change_timezone_respects_cooldown():
    recent = datetime.now(timezone.utc) - timedelta(days=5)
    old = datetime.now(timezone.utc) - timedelta(days=31)

    assert can_change_timezone(_user("UTC", timezone_changed_at=recent)) is False
    assert can_change_timezone(_user("UTC", timezone_changed_at=old)) is True
