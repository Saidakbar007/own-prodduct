"""app/services/checkin_service.py — чек-ин и режим восстановления (§9, §11)."""

import json
from datetime import date, datetime, timedelta, timezone

from app.auth import hash_password
from app.models import Habit, SeasonDay, User
from app.services.checkin_service import (
    energy_last_n_days,
    is_in_recovery_mode,
    log_checkin,
    missed_count_last_7_days,
    should_offer_recovery_mode,
    start_recovery_mode,
    stress_last_n_days,
)
from app.services.seasons import create_season


def _make_user(db_session, login):
    user = User(login=login, email=f"{login}@example.com", password_hash=hash_password("pw"), name="Т", birth_year=1995)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_log_checkin_upserts_same_day(db_session, unique):
    user = _make_user(db_session, f"chk-a-{unique}")
    today = date(2026, 11, 10)
    log_checkin(db_session, user.id, today, energy=3, stress=2, mood=4)
    checkin = log_checkin(db_session, user.id, today, energy=5, stress=1, mood=5)
    assert checkin.energy == 5
    assert energy_last_n_days(db_session, user.id, today, 1) == [5]


def test_recovery_mode_offered_after_three_low_energy_days(db_session, unique):
    user = _make_user(db_session, f"chk-b-{unique}")
    today = date(2026, 11, 10)
    for offset in (0, 1, 2):
        log_checkin(db_session, user.id, today - timedelta(days=offset), energy=2, stress=3, mood=3)
    assert should_offer_recovery_mode(db_session, user.id, today) is True


def test_recovery_mode_not_offered_with_normal_energy(db_session, unique):
    user = _make_user(db_session, f"chk-c-{unique}")
    today = date(2026, 11, 10)
    for offset in (0, 1, 2):
        log_checkin(db_session, user.id, today - timedelta(days=offset), energy=4, stress=2, mood=4)
    assert should_offer_recovery_mode(db_session, user.id, today) is False


def test_recovery_mode_lifecycle_start_and_expire(db_session, unique):
    user = _make_user(db_session, f"chk-d-{unique}")
    today = date(2026, 11, 10)
    for offset in (0, 1, 2):
        log_checkin(db_session, user.id, today - timedelta(days=offset), energy=1, stress=4, mood=2)
    assert should_offer_recovery_mode(db_session, user.id, today) is True

    start_recovery_mode(db_session, user.id, "tired", now=datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc))
    assert is_in_recovery_mode(db_session, user.id, today) is True
    # Пока активен — повторно не предлагаем
    assert should_offer_recovery_mode(db_session, user.id, today) is False
    # Через 8 дней режим истёк
    assert is_in_recovery_mode(db_session, user.id, today + timedelta(days=8)) is False


def test_missed_count_includes_season_days_and_habits(db_session, unique):
    user = _make_user(db_session, f"chk-e-{unique}")
    today = date(2026, 11, 10)

    season = create_season(db_session, user.id, "pushups_50", 30, 5, today - timedelta(days=5))
    days = db_session.exec(
        __import__("sqlmodel").select(SeasonDay).where(SeasonDay.season_id == season.id)
    ).all()
    missed_days = [d for d in days if d.calendar_date < today and d.kind != "rest"][:2]
    for d in missed_days:
        d.status = "missed"
        db_session.add(d)
    db_session.add(
        Habit(uid=user.id, title="Привычка", spheres_json="[]", days_json=json.dumps([today.isoweekday()]), duration_min=5, minimal_version="2 мин")
    )
    db_session.commit()

    count = missed_count_last_7_days(db_session, user.id, today)
    assert count >= len(missed_days)
