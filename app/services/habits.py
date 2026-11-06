"""
Привычки и плохие привычки (§10 docs/specs/NEWLIFE_V8_SPEC.md): создание, лог "в один
тап", серия без обнуления (§9 "не пропускай дважды" — один пропуск не рвёт
серию, два подряд — рвёт), % выполнения за неделю, тренд плохой привычки.
"""

from datetime import date, timedelta
from typing import Optional

from sqlmodel import Session, select

from app.models import BadHabit, BadHabitLog, Habit, HabitLog


def log_habit(db: Session, habit_id: int, on_date: date, status: str, now) -> HabitLog:
    """Один лог на привычку в день — повторная отметка перезаписывает статус."""
    existing = db.exec(
        select(HabitLog).where(HabitLog.habit_id == habit_id, HabitLog.log_date == on_date)
    ).first()
    if existing:
        existing.status = status
        existing.at = now
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing
    log = HabitLog(habit_id=habit_id, log_date=on_date, status=status, at=now)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def habit_logs_by_date(db: Session, habit_id: int) -> dict[date, str]:
    logs = db.exec(select(HabitLog).where(HabitLog.habit_id == habit_id)).all()
    return {log.log_date: log.status for log in logs}


def habit_streak(db: Session, habit: Habit, upto: date) -> int:
    """Серия без обнуления (§9/§10): идём назад по дням, когда привычка
    должна была выполняться (habit.days_json). "done"/"minimal" продолжают
    серию; один пропущенный ПОДРЯД день (без лога или "missed") терпим —
    но два пропуска подряд обрывают серию ("не пропускай дважды", §9)."""
    logs = habit_logs_by_date(db, habit.id)
    import json

    active_weekdays = set(json.loads(habit.days_json))
    if not active_weekdays:
        return 0

    streak = 0
    consecutive_misses = 0
    cursor = upto
    # upto (сегодня) может быть ещё не отмечен — не считаем это пропуском.
    if cursor.isoweekday() in active_weekdays and cursor not in logs:
        cursor -= timedelta(days=1)

    while True:
        if cursor.isoweekday() not in active_weekdays:
            cursor -= timedelta(days=1)
            if (upto - cursor).days > 366:
                break
            continue
        status = logs.get(cursor)
        if status in ("done", "minimal"):
            streak += 1
            consecutive_misses = 0
        else:
            consecutive_misses += 1
            if consecutive_misses >= 2:
                break
        cursor -= timedelta(days=1)
        if (upto - cursor).days > 366:
            break
    return streak


def week_completion_rate(db: Session, habit: Habit, week_start: date) -> float:
    """Доля дней недели (из тех, что по расписанию привычки), где она
    отмечена done/minimal."""
    import json

    active_weekdays = set(json.loads(habit.days_json))
    logs = habit_logs_by_date(db, habit.id)
    scheduled = [week_start + timedelta(days=i) for i in range(7) if (week_start + timedelta(days=i)).isoweekday() in active_weekdays]
    if not scheduled:
        return 0.0
    done = sum(1 for d in scheduled if logs.get(d) in ("done", "minimal"))
    return done / len(scheduled)


def log_bad_habit_slip(db: Session, bad_habit_id: int, on_date: date, trigger_id: Optional[str], now) -> BadHabitLog:
    """Лог в один тап: "сорвался" (+1 к значению за день) + опционально триггер."""
    existing = db.exec(
        select(BadHabitLog).where(BadHabitLog.bad_habit_id == bad_habit_id, BadHabitLog.log_date == on_date)
    ).first()
    if existing:
        existing.value += 1
        existing.trigger_id = trigger_id or existing.trigger_id
        existing.at = now
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing
    log = BadHabitLog(bad_habit_id=bad_habit_id, log_date=on_date, value=1, trigger_id=trigger_id, at=now)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def bad_habit_recent_average(db: Session, bad_habit_id: int, upto: date, window_days: int = 7) -> Optional[float]:
    """Среднее значение в день за последние window_days (включая дни без
    срывов — value=0) — тренд вниз, не "ноль сразу" (§10)."""
    logs = db.exec(select(BadHabitLog).where(BadHabitLog.bad_habit_id == bad_habit_id)).all()
    by_date = {log.log_date: log.value for log in logs}
    days = [upto - timedelta(days=i) for i in range(window_days)]
    if not any(d in by_date for d in days):
        return None
    return sum(by_date.get(d, 0) for d in days) / window_days


def most_common_trigger(db: Session, bad_habit_id: int) -> Optional[str]:
    logs = db.exec(
        select(BadHabitLog).where(BadHabitLog.bad_habit_id == bad_habit_id, BadHabitLog.trigger_id.is_not(None))
    ).all()
    if not logs:
        return None
    counts: dict[str, int] = {}
    for log in logs:
        counts[log.trigger_id] = counts.get(log.trigger_id, 0) + 1
    return max(counts, key=counts.get)
