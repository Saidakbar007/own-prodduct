"""
Связывает app/newlife/scheduler.py (чистые функции) с БД: собирает входные
данные пользователя на дату (режим, обязательные дела, действия сезонов,
привычки, задачи), запускает планировщик и сохраняет ScheduleBlock (§6, §14).
"""

import json
from datetime import date, timedelta
from typing import Optional

from sqlmodel import Session, select

from app.models import Commitment, Habit, Profile, ScheduleBlock, Season, SeasonDay, Task, User
from app.newlife import scheduler as sch
from app.newlife.rounding import round_run_time_seconds  # noqa: F401  (переиспользуется UI-слоем)
from app.services.seasons import get_active_seasons, today_day_number

DEFAULT_WAKE = "07:00"
DEFAULT_SLEEP = "23:00"
DEFAULT_DAILY_MINUTES = 30
HEAVY_MIN_DURATION = 30  # §6 п.4: тренировки/учёба >= 30 мин — "тяжёлое"


def _weekday(d: date) -> int:
    """1..7, пн..вс — как в Commitment.weekdays_json/Habit.days_json."""
    return d.isoweekday()


def _commitment_fixed_blocks(db: Session, uid: int, on_date: date) -> list[sch.FixedBlock]:
    weekday = _weekday(on_date)
    commitments = db.exec(select(Commitment).where(Commitment.uid == uid, Commitment.active.is_(True))).all()
    blocks = []
    for c in commitments:
        if weekday in json.loads(c.weekdays_json):
            blocks.append(
                sch.FixedBlock(
                    start_min=sch.parse_hhmm(c.start_time),
                    end_min=sch.parse_hhmm(c.end_time),
                    kind="commitment",
                    title=c.title,
                    ref_type="commitment",
                    ref_id=c.id,
                )
            )
    return blocks


def _goal_action_candidates(
    db: Session, uid: int, on_date: date, exclude_refs: set[tuple[str, int]]
) -> list[sch.Candidate]:
    candidates = []
    for season in get_active_seasons(db, uid):
        day_number = today_day_number(season, on_date)
        day = db.exec(
            select(SeasonDay).where(SeasonDay.season_id == season.id, SeasonDay.day_number == day_number)
        ).first()
        if not day or day.kind == "rest" or day.status != "planned" or ("season_day", day.id) in exclude_refs:
            continue
        duration = season.minutes_per_day
        candidates.append(
            sch.Candidate(
                kind="goal_action",
                title=day.title,
                duration_min=duration,
                ref_type="season_day",
                ref_id=day.id,
                heavy=duration >= HEAVY_MIN_DURATION,
                minimal_duration_min=min(10, duration),
            )
        )
    return candidates


def _habit_candidates(
    db: Session, uid: int, on_date: date, exclude_refs: set[tuple[str, int]]
) -> list[sch.Candidate]:
    weekday = _weekday(on_date)
    habits = db.exec(select(Habit).where(Habit.uid == uid, Habit.active.is_(True))).all()
    candidates = []
    for h in habits:
        if weekday not in json.loads(h.days_json) or ("habit", h.id) in exclude_refs:
            continue
        candidates.append(
            sch.Candidate(
                kind="habit",
                title=h.title,
                duration_min=h.duration_min,
                ref_type="habit",
                ref_id=h.id,
                heavy=h.duration_min >= HEAVY_MIN_DURATION,
                minimal_duration_min=2,  # §9 "правило двух минут" — минимальная версия всегда есть
            )
        )
    return candidates


def _task_candidates(
    db: Session, uid: int, on_date: date, exclude_refs: set[tuple[str, int]]
) -> list[sch.Candidate]:
    tasks = db.exec(
        select(Task).where(Task.uid == uid, Task.task_date == on_date, Task.status == "planned", Task.start_time.is_(None))
    ).all()
    candidates = []
    for t in tasks:
        if ("task", t.id) in exclude_refs:
            continue
        deadline_days = (t.deadline - on_date).days if t.deadline else None
        candidates.append(
            sch.Candidate(
                kind="task",
                title=t.title,
                duration_min=t.duration_min,
                ref_type="task",
                ref_id=t.id,
                heavy=False,
                eisenhower=t.priority,
                deadline_days=deadline_days,
            )
        )
    return candidates


def _task_fixed_blocks(db: Session, uid: int, on_date: date) -> list[sch.FixedBlock]:
    tasks = db.exec(
        select(Task).where(Task.uid == uid, Task.task_date == on_date, Task.status == "planned", Task.start_time.is_not(None))
    ).all()
    return [
        sch.FixedBlock(
            start_min=sch.parse_hhmm(t.start_time),
            end_min=sch.parse_hhmm(t.start_time) + t.duration_min,
            kind="task_fixed",
            title=t.title,
            ref_type="task",
            ref_id=t.id,
        )
        for t in tasks
    ]


def build_schedule_for_day(
    db: Session, user: User, on_date: date, moved_blocks: Optional[list[ScheduleBlock]] = None
) -> sch.DayScheduleResult:
    """Собирает и расставляет день, НЕ сохраняя в БД (чистый просмотр).
    moved_blocks — уже перетащенные пользователем блоки этого дня (§6 п.8):
    занимают своё новое время как неподвижные и не планируются заново."""
    moved_blocks = moved_blocks or []
    profile = db.exec(select(Profile).where(Profile.uid == user.id)).first()
    wake = profile.wake_time if profile and profile.wake_time else DEFAULT_WAKE
    sleep = profile.sleep_time if profile and profile.sleep_time else DEFAULT_SLEEP
    chronotype = profile.chronotype if profile and profile.chronotype else "varies"
    daily_minutes = profile.daily_minutes if profile and profile.daily_minutes else DEFAULT_DAILY_MINUTES

    wake_min = sch.parse_hhmm(wake)
    sleep_min = sch.parse_hhmm(sleep)
    day_end = sleep_min if sleep_min > wake_min else sleep_min + 24 * 60

    exclude_refs = {(b.ref_type, b.ref_id) for b in moved_blocks if b.ref_type and b.ref_id}
    moved_fixed = [
        sch.FixedBlock(
            start_min=sch.parse_hhmm(b.start_time), end_min=sch.parse_hhmm(b.end_time),
            kind="commitment", title=b.title, ref_type=b.ref_type, ref_id=b.ref_id,
        )
        for b in moved_blocks
    ]

    fixed = moved_fixed + _commitment_fixed_blocks(db, user.id, on_date) + _task_fixed_blocks(db, user.id, on_date)
    goal_actions = _goal_action_candidates(db, user.id, on_date, exclude_refs)
    habits = _habit_candidates(db, user.id, on_date, exclude_refs)
    tasks = _task_candidates(db, user.id, on_date, exclude_refs)

    return sch.build_day_schedule(
        fixed_blocks=fixed,
        day_start_min=wake_min,
        day_end_min=day_end,
        goal_actions=goal_actions,
        habits=habits,
        tasks=tasks,
        chronotype=chronotype,
        daily_minutes_limit=daily_minutes,
    )


def sync_schedule_for_day(db: Session, user: User, on_date: date) -> list[ScheduleBlock]:
    """Пересчитывает и сохраняет расписание дня (§6 п.7: при новом деле,
    пропуске, переносе, низкой энергии — вызывается заново). Блоки, которые
    человек перетащил (moved_by_user=True), не трогаем и не планируем поверх
    них — они считаются неподвижными для этого пересчёта."""
    existing = db.exec(
        select(ScheduleBlock).where(ScheduleBlock.uid == user.id, ScheduleBlock.block_date == on_date)
    ).all()
    moved = [b for b in existing if b.moved_by_user]
    for b in existing:
        if not b.moved_by_user:
            db.delete(b)
    db.commit()

    result = build_schedule_for_day(db, user, on_date, moved_blocks=moved)

    saved: list[ScheduleBlock] = list(moved)
    for placed in result.blocks:
        block = ScheduleBlock(
            uid=user.id,
            block_date=on_date,
            start_time=sch.format_hhmm(placed.start_min),
            end_time=sch.format_hhmm(placed.end_min),
            kind=placed.kind,
            ref_type=placed.ref_type,
            ref_id=placed.ref_id,
            title=placed.title,
            status="planned",
        )
        db.add(block)
        saved.append(block)
    db.commit()
    for b in saved:
        db.refresh(b)
    return sorted(saved, key=lambda b: b.start_time)


def get_or_build_schedule_for_day(db: Session, user: User, on_date: date) -> list[ScheduleBlock]:
    existing = db.exec(
        select(ScheduleBlock).where(ScheduleBlock.uid == user.id, ScheduleBlock.block_date == on_date)
    ).all()
    if existing:
        return sorted(existing, key=lambda b: b.start_time)
    return sync_schedule_for_day(db, user, on_date)


def week_dates(reference: date) -> list[date]:
    """Понедельник..воскресенье недели, в которую попадает reference."""
    monday = reference - timedelta(days=reference.weekday())
    return [monday + timedelta(days=i) for i in range(7)]
