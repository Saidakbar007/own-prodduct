"""Недельная продуктивность (NEWLIFE_2_0.md §3.1 — столбцы Пн-Вс для Главной)."""

import json
from datetime import date, timedelta

from app.models import Habit, HabitLog, User
from app.services.productivity import day_completion_percent, week_productivity
from sqlmodel import select

THIS_YEAR = date.today().year


def _register_payload(unique: str, **overrides):
    payload = {
        "name": "Продуктивность Тест",
        "birth_year": THIS_YEAR - 25,
        "age_confirm": "1",
        "email": f"prod-{unique}@example.com",
        "login": f"prod-{unique}",
        "password": "s3cret-pass",
        "password_confirm": "s3cret-pass",
        "timezone": "UTC",
    }
    payload.update(overrides)
    return payload


def _register(client, unique):
    reg = client.post("/register", data=_register_payload(unique), follow_redirects=True)
    assert reg.status_code == 200


def test_day_with_no_plan_is_none(client, unique, db_session):
    _register(client, unique)
    uid = db_session.exec(select(User).where(User.login == f"prod-{unique}")).first().id
    assert day_completion_percent(db_session, uid, date.today()) is None


def test_day_completion_counts_due_habits(client, unique, db_session):
    _register(client, unique)
    uid = db_session.exec(select(User).where(User.login == f"prod-{unique}")).first().id
    today = date.today()

    h1 = Habit(
        uid=uid, catalog_id=None, title="A",
        spheres_json=json.dumps(["body"]), days_json=json.dumps(list(range(1, 8))),
        time_pref="morning", duration_min=5, minimal_version="min",
    )
    h2 = Habit(
        uid=uid, catalog_id=None, title="B",
        spheres_json=json.dumps(["body"]), days_json=json.dumps(list(range(1, 8))),
        time_pref="morning", duration_min=5, minimal_version="min",
    )
    db_session.add(h1)
    db_session.add(h2)
    db_session.commit()
    db_session.refresh(h1)
    db_session.refresh(h2)

    db_session.add(HabitLog(habit_id=h1.id, log_date=today, status="done"))
    db_session.commit()

    percent = day_completion_percent(db_session, uid, today)
    assert percent == 50


def test_week_productivity_returns_7_days(client, unique, db_session):
    _register(client, unique)
    uid = db_session.exec(select(User).where(User.login == f"prod-{unique}")).first().id
    monday = date.today() - timedelta(days=date.today().isoweekday() - 1)
    week = week_productivity(db_session, uid, monday)
    assert len(week) == 7
    assert week[0]["date"] == monday
    assert sum(1 for d in week if d["is_today"]) == 1
