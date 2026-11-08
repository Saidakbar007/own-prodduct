"""Паутинка Главной/Прогресса (NEWLIFE_2_0.md §3.1/§3.4) — app/services/progress.py."""

import json
from datetime import date, timedelta

from app.models import Habit, HabitLog, SphereState, User
from app.services.progress import sphere_radar_values, sphere_recent_score
from sqlmodel import select

THIS_YEAR = date.today().year


def _register_payload(unique: str, **overrides):
    payload = {
        "name": "Радар Тест",
        "birth_year": THIS_YEAR - 25,
        "age_confirm": "1",
        "email": f"radar-{unique}@example.com",
        "login": f"radar-{unique}",
        "password": "s3cret-pass",
        "password_confirm": "s3cret-pass",
        "timezone": "UTC",
    }
    payload.update(overrides)
    return payload


def _register(client, unique):
    reg = client.post("/register", data=_register_payload(unique), follow_redirects=True)
    assert reg.status_code == 200


def test_sphere_without_activity_scores_zero(client, unique, db_session):
    _register(client, unique)
    uid = db_session.exec(select(User).where(User.login == f"radar-{unique}")).first().id
    assert sphere_recent_score(db_session, uid, "mind", date.today()) == 0


def test_sphere_with_all_habits_done_scores_ten(client, unique, db_session):
    _register(client, unique)
    uid = db_session.exec(select(User).where(User.login == f"radar-{unique}")).first().id
    today = date.today()

    h = Habit(
        uid=uid, catalog_id=None, title="Медитация",
        spheres_json=json.dumps(["mind"]), days_json=json.dumps(list(range(1, 8))),
        time_pref="morning", duration_min=10, minimal_version="min",
    )
    db_session.add(h)
    db_session.commit()
    db_session.refresh(h)

    for i in range(14):
        d = today - timedelta(days=i)
        db_session.add(HabitLog(habit_id=h.id, log_date=d, status="done"))
    db_session.commit()

    assert sphere_recent_score(db_session, uid, "mind", today) == 10


def test_radar_values_include_baseline_from_sphere_state(client, unique, db_session):
    _register(client, unique)
    uid = db_session.exec(select(User).where(User.login == f"radar-{unique}")).first().id

    db_session.add(SphereState(uid=uid, sphere_id="body", level=7, priority=1, active=True))
    db_session.commit()

    values = sphere_radar_values(db_session, uid, date.today())
    body_row = next(v for v in values if v["sphere_id"] == "body")
    assert body_row["baseline"] == 7
    assert body_row["current"] == 0  # нет активности за 14 дней
    assert body_row["active"] is True
