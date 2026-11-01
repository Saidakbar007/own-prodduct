"""app/services/schedule_service.py — сборка и сохранение расписания дня
(§6, §14): собирает обязательные дела/действия сезона/привычки/задачи
пользователя и прогоняет через app/newlife/scheduler.py."""

import json
from datetime import date, timedelta

from sqlmodel import select

from app.auth import hash_password
from app.models import Commitment, Habit, Profile, ScheduleBlock, Task, User
from app.services.schedule_service import (
    get_or_build_schedule_for_day,
    sync_schedule_for_day,
    week_dates,
)


def _make_user(db_session, login, **profile_kwargs):
    user = User(
        login=login,
        email=f"{login}@example.com",
        password_hash=hash_password("pw"),
        name=f"Юзер {login}",
        birth_year=1995,
        timezone="UTC",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    if profile_kwargs:
        profile = Profile(uid=user.id, **profile_kwargs)
        db_session.add(profile)
        db_session.commit()
    return user


def test_habit_gets_scheduled_into_free_window(db_session, unique):
    user = _make_user(db_session, f"sched-a-{unique}", wake_time="07:00", sleep_time="23:00", daily_minutes=60)
    monday = date(2026, 11, 2)
    db_session.add(
        Habit(
            uid=user.id, title="Вода с утра", spheres_json="[]",
            days_json=json.dumps([monday.isoweekday()]), duration_min=5, minimal_version="1 стакан",
        )
    )
    db_session.commit()

    blocks = sync_schedule_for_day(db_session, user, monday)
    assert any(b.title == "Вода с утра" for b in blocks)


def test_commitment_blocks_out_time_from_scheduling(db_session, unique):
    user = _make_user(db_session, f"sched-b-{unique}", wake_time="07:00", sleep_time="23:00", daily_minutes=60)
    monday = date(2026, 11, 2)
    weekday = monday.isoweekday()
    db_session.add(
        Commitment(
            uid=user.id, title="Работа", category="work",
            weekdays_json=json.dumps([weekday]), start_time="07:00", end_time="22:50",
        )
    )
    db_session.add(
        Habit(uid=user.id, title="Растяжка", spheres_json="[]", days_json=json.dumps([weekday]), duration_min=10, minimal_version="2 мин")
    )
    db_session.commit()

    blocks = sync_schedule_for_day(db_session, user, monday)
    habit_block = next(b for b in blocks if b.title == "Растяжка")
    # Единственное окно — 22:50..23:00 (10 минут), после рабочего дня.
    assert habit_block.start_time == "22:50"


def test_resync_preserves_blocks_moved_by_user(db_session, unique):
    user = _make_user(db_session, f"sched-c-{unique}", wake_time="07:00", sleep_time="23:00", daily_minutes=60)
    monday = date(2026, 11, 2)
    db_session.add(
        Habit(uid=user.id, title="Чтение", spheres_json="[]", days_json=json.dumps([monday.isoweekday()]), duration_min=15, minimal_version="1 страница")
    )
    db_session.commit()

    first = sync_schedule_for_day(db_session, user, monday)
    block = next(b for b in first if b.title == "Чтение")
    block.moved_by_user = True
    block.start_time = "21:00"
    block.end_time = "21:15"
    db_session.add(block)
    db_session.commit()

    second = sync_schedule_for_day(db_session, user, monday)
    moved = [b for b in second if b.title == "Чтение"]
    assert len(moved) == 1
    assert moved[0].id == block.id
    assert moved[0].start_time == "21:00"
    assert moved[0].moved_by_user is True


def test_get_or_build_reuses_existing_blocks_without_duplicating(db_session, unique):
    user = _make_user(db_session, f"sched-d-{unique}", wake_time="07:00", sleep_time="23:00", daily_minutes=60)
    monday = date(2026, 11, 2)
    db_session.add(
        Habit(uid=user.id, title="Планка", spheres_json="[]", days_json=json.dumps([monday.isoweekday()]), duration_min=5, minimal_version="30 сек")
    )
    db_session.commit()

    first = get_or_build_schedule_for_day(db_session, user, monday)
    second = get_or_build_schedule_for_day(db_session, user, monday)
    assert [b.id for b in first] == [b.id for b in second]

    all_blocks = db_session.exec(select(ScheduleBlock).where(ScheduleBlock.uid == user.id)).all()
    assert len(all_blocks) == 1


def test_task_with_fixed_time_blocks_that_slot(db_session, unique):
    user = _make_user(db_session, f"sched-e-{unique}", wake_time="07:00", sleep_time="23:00", daily_minutes=60)
    monday = date(2026, 11, 2)
    db_session.add(
        Task(uid=user.id, title="Созвон", task_date=monday, start_time="09:00", duration_min=60, priority="do", status="planned")
    )
    db_session.add(
        Habit(uid=user.id, title="Зарядка", spheres_json="[]", days_json=json.dumps([monday.isoweekday()]), duration_min=10, minimal_version="2 мин")
    )
    db_session.commit()

    blocks = sync_schedule_for_day(db_session, user, monday)
    zaryadka = next(b for b in blocks if b.title == "Зарядка")
    assert not ("09:00" <= zaryadka.start_time < "10:00")


def test_week_dates_returns_monday_to_sunday():
    wednesday = date(2026, 11, 4)
    days = week_dates(wednesday)
    assert len(days) == 7
    assert days[0] == date(2026, 11, 2)  # понедельник
    assert days[-1] == date(2026, 11, 8)  # воскресенье
    assert days[0].isoweekday() == 1
