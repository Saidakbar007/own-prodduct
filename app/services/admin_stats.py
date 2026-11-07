"""
Дашборд админки (§13 ТЗ; маршрут /admin и /admin/analytics — алиасы одного
и того же дашборда): воронка онбординга, удержание D1/D7/D30 по когортам,
доля дошедших до Reveal, доля начавших следующий сезон, вирусность
(принятые вызовы на пользователя), популярность сфер. Админы и demo-
аккаунт исключены из всех чисел (доп. задача, см. DECISIONS.md) — иначе
ручное тестирование искажало бы метрики продукта.
"""

import os
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlmodel import Session, func, select

from app.models import Challenge, Event, Season, SphereState, User

FUNNEL_STEPS = ["onboarding_started", "trailer_shown", "signup", "season_started"]
RETENTION_HORIZONS = (1, 7, 30)
DEMO_LOGIN = "demo"


def _excluded_uids(db: Session) -> set[int]:
    """Админы (ADMIN_LOGINS) и demo-аккаунт — не считаются в продуктовой
    аналитике (ручное тестирование не должно искажать метрики)."""
    admin_logins = {login.strip() for login in os.getenv("ADMIN_LOGINS", "").split(",") if login.strip()}
    excluded_logins = admin_logins | {DEMO_LOGIN}
    if not excluded_logins:
        return set()
    rows = db.exec(select(User.id).where(User.login.in_(excluded_logins))).all()
    return set(rows)


def funnel_counts(db: Session) -> dict[str, int]:
    excluded = _excluded_uids(db)
    counts = {}
    for step in FUNNEL_STEPS:
        query = select(func.count()).select_from(Event).where(Event.event_type == step)
        if excluded:
            query = query.where(Event.uid.is_(None) | Event.uid.notin_(excluded))
        counts[step] = db.exec(query).one()
    return counts


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


def retention_for_cohort(db: Session, cohort_day: date, horizon_days: int) -> dict:
    """Доля подписавшихся в cohort_day, у кого есть активность через
    horizon_days дней (день отметки, замер)."""
    excluded = _excluded_uids(db)
    cohort_start, cohort_end = _day_bounds(cohort_day)
    cohort_uids = set(
        db.exec(
            select(Event.uid).where(
                Event.event_type == "signup", Event.created_at >= cohort_start, Event.created_at < cohort_end
            )
        ).all()
    ) - {None} - excluded

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


def _excluding(query, excluded: set[int]):
    if excluded:
        return query.where(Event.uid.is_(None) | Event.uid.notin_(excluded))
    return query


def reveal_completion_rate(db: Session) -> Optional[float]:
    excluded = _excluded_uids(db)
    started = db.exec(
        _excluding(select(func.count()).select_from(Event).where(Event.event_type == "season_started"), excluded)
    ).one()
    if not started:
        return None
    revealed = db.exec(
        _excluding(
            select(func.count(func.distinct(Event.season_id))).where(Event.event_type == "reveal_viewed"), excluded
        )
    ).one()
    return revealed / started


def next_season_rate(db: Session) -> Optional[float]:
    excluded = _excluded_uids(db)
    revealed = db.exec(
        _excluding(
            select(func.count(func.distinct(Event.season_id))).where(Event.event_type == "reveal_viewed"), excluded
        )
    ).one()
    if not revealed:
        return None
    next_started = db.exec(
        _excluding(
            select(func.count()).select_from(Event).where(Event.event_type == "next_season_started"), excluded
        )
    ).one()
    return next_started / revealed


def sphere_popularity(db: Session) -> list[tuple[str, int]]:
    """Сколько человек (исключая админов/demo) держат сферу активной —
    популярность по убыванию."""
    excluded = _excluded_uids(db)
    query = select(SphereState.sphere_id, func.count(func.distinct(SphereState.uid))).where(
        SphereState.active.is_(True)
    )
    if excluded:
        query = query.where(SphereState.uid.notin_(excluded))
    query = query.group_by(SphereState.sphere_id)
    rows = db.exec(query).all()
    return sorted(rows, key=lambda row: row[1], reverse=True)


def virality(db: Session) -> Optional[float]:
    """Принятые вызовы на пользователя — вирусность (§13)."""
    excluded = _excluded_uids(db)
    users_query = select(func.count()).select_from(User)
    if excluded:
        users_query = users_query.where(User.id.notin_(excluded))
    total_users = db.exec(users_query).one()
    if not total_users:
        return None
    challenge_query = select(func.count()).select_from(Challenge).where(Challenge.status.in_(["active", "finished"]))
    if excluded:
        challenge_query = challenge_query.where(
            Challenge.from_uid.notin_(excluded), Challenge.to_uid.notin_(excluded)
        )
    accepted = db.exec(challenge_query).one()
    return accepted / total_users
