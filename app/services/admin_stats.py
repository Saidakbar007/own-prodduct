"""
Дашборд админки (§13 ТЗ): воронка онбординга, удержание D1/D7/D30 по
когортам, доля дошедших до Reveal, доля начавших следующий сезон,
вирусность (принятые вызовы на пользователя).
"""

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlmodel import Session, func, select

from app.models import Challenge, Event, User

FUNNEL_STEPS = ["onboarding_started", "trailer_shown", "signup", "prologue_started", "season_started"]
RETENTION_HORIZONS = (1, 7, 30)


def funnel_counts(db: Session) -> dict[str, int]:
    return {
        step: db.exec(select(func.count()).select_from(Event).where(Event.event_type == step)).one()
        for step in FUNNEL_STEPS
    }


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


def retention_for_cohort(db: Session, cohort_day: date, horizon_days: int) -> dict:
    """Доля подписавшихся в cohort_day, у кого есть активность через
    horizon_days дней (день отметки, замер)."""
    cohort_start, cohort_end = _day_bounds(cohort_day)
    cohort_uids = set(
        db.exec(
            select(Event.uid).where(
                Event.event_type == "signup", Event.created_at >= cohort_start, Event.created_at < cohort_end
            )
        ).all()
    ) - {None}

    if not cohort_uids:
        return {"cohort_day": cohort_day, "horizon": horizon_days, "cohort_size": 0, "retained": 0, "rate": None}

    window_start = cohort_start + timedelta(days=horizon_days)
    window_end = window_start + timedelta(days=1)
    active_uids = set(
        db.exec(
            select(Event.uid).where(
                Event.event_type.in_(["day_done", "day_minimal", "measurement_logged"]),
                Event.uid.in_(cohort_uids),
                Event.created_at >= window_start,
                Event.created_at < window_end,
            )
        ).all()
    )
    retained = len(active_uids)
    return {
        "cohort_day": cohort_day,
        "horizon": horizon_days,
        "cohort_size": len(cohort_uids),
        "retained": retained,
        "rate": retained / len(cohort_uids),
    }


def retention_overview(db: Session, cohort_day: date) -> list[dict]:
    return [retention_for_cohort(db, cohort_day, h) for h in RETENTION_HORIZONS]


def reveal_completion_rate(db: Session) -> Optional[float]:
    started = db.exec(select(func.count()).select_from(Event).where(Event.event_type == "season_started")).one()
    if not started:
        return None
    revealed = db.exec(
        select(func.count(func.distinct(Event.season_id))).where(Event.event_type == "reveal_viewed")
    ).one()
    return revealed / started


def next_season_rate(db: Session) -> Optional[float]:
    revealed = db.exec(
        select(func.count(func.distinct(Event.season_id))).where(Event.event_type == "reveal_viewed")
    ).one()
    if not revealed:
        return None
    next_started = db.exec(
        select(func.count()).select_from(Event).where(Event.event_type == "next_season_started")
    ).one()
    return next_started / revealed


def virality(db: Session) -> Optional[float]:
    """Принятые вызовы на пользователя — вирусность (§13)."""
    total_users = db.exec(select(func.count()).select_from(User)).one()
    if not total_users:
        return None
    accepted = db.exec(
        select(func.count()).select_from(Challenge).where(Challenge.status.in_(["active", "finished"]))
    ).one()
    return accepted / total_users
