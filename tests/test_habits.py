"""app/services/habits.py — лог привычек, серия без обнуления (§9/§10),
% за неделю, тренд плохой привычки."""

import json
from datetime import date, datetime, timedelta, timezone

from app.auth import hash_password
from app.models import BadHabit, Habit, User
from app.services.habits import (
    bad_habit_recent_average,
    habit_streak,
    log_bad_habit_slip,
    log_habit,
    most_common_trigger,
    week_completion_rate,
)

NOW = datetime.now(timezone.utc)
EVERY_DAY = json.dumps([1, 2, 3, 4, 5, 6, 7])


def _make_user(db_session, login):
    user = User(login=login, email=f"{login}@example.com", password_hash=hash_password("pw"), name="Т", birth_year=1995)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_habit(db_session, uid, days_json=EVERY_DAY):
    habit = Habit(uid=uid, title="Привычка", spheres_json="[]", days_json=days_json, duration_min=5, minimal_version="2 мин")
    db_session.add(habit)
    db_session.commit()
    db_session.refresh(habit)
    return habit


def test_streak_counts_consecutive_done_days(db_session, unique):
    user = _make_user(db_session, f"habit-a-{unique}")
    habit = _make_habit(db_session, user.id)
    today = date(2026, 11, 10)
    for offset in (0, 1, 2):
        log_habit(db_session, habit.id, today - timedelta(days=offset), "done", NOW)
    assert habit_streak(db_session, habit, today) == 3


def test_streak_tolerates_single_gap_but_not_two_in_a_row(db_session, unique):
    user = _make_user(db_session, f"habit-b-{unique}")
    habit = _make_habit(db_session, user.id)
    today = date(2026, 11, 10)
    log_habit(db_session, habit.id, today, "done", NOW)
    # today-1 отсутствует в логах (один пропуск — терпим)
    log_habit(db_session, habit.id, today - timedelta(days=2), "done", NOW)
    log_habit(db_session, habit.id, today - timedelta(days=3), "done", NOW)
    assert habit_streak(db_session, habit, today) == 3


def test_streak_breaks_after_two_consecutive_misses(db_session, unique):
    user = _make_user(db_session, f"habit-c-{unique}")
    habit = _make_habit(db_session, user.id)
    today = date(2026, 11, 10)
    log_habit(db_session, habit.id, today, "done", NOW)
    # today-1 и today-2 оба без логов -> два пропуска подряд
    log_habit(db_session, habit.id, today - timedelta(days=3), "done", NOW)
    assert habit_streak(db_session, habit, today) == 1


def test_streak_does_not_punish_unlogged_today(db_session, unique):
    user = _make_user(db_session, f"habit-d-{unique}")
    habit = _make_habit(db_session, user.id)
    today = date(2026, 11, 10)
    log_habit(db_session, habit.id, today - timedelta(days=1), "done", NOW)
    log_habit(db_session, habit.id, today - timedelta(days=2), "done", NOW)
    assert habit_streak(db_session, habit, today) == 2


def test_week_completion_rate(db_session, unique):
    user = _make_user(db_session, f"habit-e-{unique}")
    habit = _make_habit(db_session, user.id, days_json=json.dumps([1, 2, 3, 4, 5]))
    monday = date(2026, 11, 2)
    log_habit(db_session, habit.id, monday, "done", NOW)
    log_habit(db_session, habit.id, monday + timedelta(days=1), "minimal", NOW)
    # Остальные 3 будних дня не отмечены -> 2/5
    assert week_completion_rate(db_session, habit, monday) == 2 / 5


def test_log_habit_overwrites_existing_log_for_same_day(db_session, unique):
    user = _make_user(db_session, f"habit-f-{unique}")
    habit = _make_habit(db_session, user.id)
    today = date(2026, 11, 10)
    log_habit(db_session, habit.id, today, "minimal", NOW)
    log_habit(db_session, habit.id, today, "done", NOW)
    assert habit_streak(db_session, habit, today) == 1


def _make_bad_habit(db_session, uid):
    bh = BadHabit(uid=uid, title="Скролл", triggers_json="[]", baseline_per_day=60, target_per_day=30, unit="minutes")
    db_session.add(bh)
    db_session.commit()
    db_session.refresh(bh)
    return bh


def test_bad_habit_slip_logged_and_trend_computed(db_session, unique):
    user = _make_user(db_session, f"habit-g-{unique}")
    bh = _make_bad_habit(db_session, user.id)
    today = date(2026, 11, 10)
    log_bad_habit_slip(db_session, bh.id, today, "boredom", NOW)
    log_bad_habit_slip(db_session, bh.id, today, "boredom", NOW)  # второй срыв в тот же день -> value=2
    log_bad_habit_slip(db_session, bh.id, today - timedelta(days=1), "boredom", NOW)
    log_bad_habit_slip(db_session, bh.id, today - timedelta(days=2), "stress", NOW)

    avg = bad_habit_recent_average(db_session, bh.id, today, window_days=7)
    assert avg == (2 + 1 + 1) / 7

    # "boredom" — триггер в 2 из 3 дней со срывами, "stress" — только в 1.
    assert most_common_trigger(db_session, bh.id) == "boredom"


def test_bad_habit_average_none_when_no_logs(db_session, unique):
    user = _make_user(db_session, f"habit-h-{unique}")
    bh = _make_bad_habit(db_session, user.id)
    assert bad_habit_recent_average(db_session, bh.id, date(2026, 11, 10)) is None
