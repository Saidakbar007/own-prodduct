"""
Чек-ин энергии/стресса/настроения (§11) и режим восстановления (§9) —
связывает app/newlife/methods.py с БД. Режим восстановления хранится как
MethodEvent(method_id="recovery_mode", accepted=True, shown_at=дата начала) —
отдельной таблицы не заводим (§4 не описывает такую, see DECISIONS.md).
"""

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlmodel import Session, select

from app.models import Checkin, HabitLog, MethodEvent, SeasonDay, Season, User
from app.newlife import methods as m


def log_checkin(db: Session, uid: int, on_date: date, energy: int, stress: int, mood: int) -> Checkin:
    existing = db.exec(select(Checkin).where(Checkin.uid == uid, Checkin.checkin_date == on_date)).first()
    if existing:
        existing.energy, existing.stress, existing.mood = energy, stress, mood
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing
    checkin = Checkin(uid=uid, checkin_date=on_date, energy=energy, stress=stress, mood=mood)
    db.add(checkin)
    db.commit()
    db.refresh(checkin)
    return checkin


def get_checkin(db: Session, uid: int, on_date: date) -> Optional[Checkin]:
    return db.exec(select(Checkin).where(Checkin.uid == uid, Checkin.checkin_date == on_date)).first()


def _recent_checkins(db: Session, uid: int, upto: date, days: int) -> list[Checkin]:
    start = upto - timedelta(days=days - 1)
    rows = db.exec(
        select(Checkin).where(Checkin.uid == uid, Checkin.checkin_date >= start, Checkin.checkin_date <= upto)
        .order_by(Checkin.checkin_date)
    ).all()
    return rows


def energy_last_n_days(db: Session, uid: int, upto: date, days: int = 3) -> list[int]:
    return [c.energy for c in _recent_checkins(db, uid, upto, days)]


def stress_last_n_days(db: Session, uid: int, upto: date, days: int = 7) -> list[int]:
    return [c.stress for c in _recent_checkins(db, uid, upto, days)]


def missed_count_last_7_days(db: Session, uid: int, upto: date) -> int:
    """§9/§11: пропуски за неделю — считаем и дни сезона (missed), и привычки
    (нет лога done/minimal в день, когда она должна была быть)."""
    start = upto - timedelta(days=6)
    count = 0

    season_ids = db.exec(select(Season.id).where(Season.uid == uid)).all()
    if season_ids:
        count += len(
            db.exec(
                select(SeasonDay.id).where(
                    SeasonDay.season_id.in_(season_ids),
                    SeasonDay.status == "missed",
                    SeasonDay.calendar_date >= start,
                    SeasonDay.calendar_date <= upto,
                )
            ).all()
        )

    import json

    from app.models import Habit

    habits = db.exec(select(Habit).where(Habit.uid == uid, Habit.active.is_(True))).all()
    for h in habits:
        days_on = set(json.loads(h.days_json))
        logs = {
            log.log_date: log.status
            for log in db.exec(
                select(HabitLog).where(HabitLog.habit_id == h.id, HabitLog.log_date >= start, HabitLog.log_date <= upto)
            ).all()
        }
        cursor = start
        while cursor <= upto:
            if cursor.isoweekday() in days_on and cursor != upto and logs.get(cursor) not in ("done", "minimal"):
                count += 1
            cursor += timedelta(days=1)

    return count


def recovery_mode_event(db: Session, uid: int) -> Optional[MethodEvent]:
    return db.exec(
        select(MethodEvent)
        .where(MethodEvent.uid == uid, MethodEvent.method_id == "recovery_mode", MethodEvent.accepted.is_(True))
        .order_by(MethodEvent.shown_at.desc())
    ).first()


def is_in_recovery_mode(db: Session, uid: int, today: date) -> bool:
    event = recovery_mode_event(db, uid)
    if not event:
        return False
    return m.is_recovery_mode_active(event.shown_at.date(), today, True)


def should_offer_recovery_mode(db: Session, uid: int, today: date) -> bool:
    if is_in_recovery_mode(db, uid, today):
        return False
    missed = missed_count_last_7_days(db, uid, today)
    energy = energy_last_n_days(db, uid, today, 3)
    return m.should_suggest_recovery_mode(missed, energy)


def start_recovery_mode(db: Session, uid: int, obstacle: Optional[str], now: Optional[datetime] = None) -> MethodEvent:
    event = MethodEvent(
        uid=uid, method_id="recovery_mode", trigger=obstacle or "unspecified",
        shown_at=now or datetime.now(timezone.utc), accepted=True,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def log_method_shown(
    db: Session, uid: int, method_id: str, trigger: str, accepted: Optional[bool] = None, now: Optional[datetime] = None
) -> MethodEvent:
    event = MethodEvent(uid=uid, method_id=method_id, trigger=trigger, shown_at=now or datetime.now(timezone.utc), accepted=accepted)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event
