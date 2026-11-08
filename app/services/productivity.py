"""
Недельная продуктивность (NEWLIFE_2_0.md §3.1 «Главная» — столбцы Пн-Вс,
высота = % выполнения плана дня, цвет от красного через жёлтый к зелёному).
День без плана (нет активных сезонов и привычек) — не 0%, а «нет данных»
(None), чтобы не красить пустой день в красный."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from sqlmodel import Session, select

from app.models import Habit, HabitLog, Season, SeasonDay


def _habit_due(habit: Habit, on_date: date) -> bool:
    import json

    days = json.loads(habit.days_json)
    return on_date.isoweekday() in days


def day_completion_percent(db: Session, uid: int, on_date: date) -> Optional[float]:
    """% выполнения плана одного дня: доля привычек (due в этот день) и
    дней сезона (kind != rest), отмеченных done/minimal/rescued."""
    total = 0
    done = 0

    habits = db.exec(select(Habit).where(Habit.uid == uid, Habit.active.is_(True))).all()
    if habits:
        logs = db.exec(
            select(HabitLog).where(
                HabitLog.habit_id.in_([h.id for h in habits]), HabitLog.log_date == on_date
            )
        ).all()
        log_by_habit = {log.habit_id: log.status for log in logs}
        for h in habits:
            if not _habit_due(h, on_date):
                continue
            total += 1
            if log_by_habit.get(h.id) in ("done", "minimal"):
                done += 1

    seasons = db.exec(select(Season).where(Season.uid == uid, Season.status == "active")).all()
    if seasons:
        season_days = db.exec(
            select(SeasonDay).where(
                SeasonDay.season_id.in_([s.id for s in seasons]),
                SeasonDay.calendar_date == on_date,
                SeasonDay.kind != "rest",
            )
        ).all()
        for sd in season_days:
            total += 1
            if sd.status in ("done", "minimal", "rescued"):
                done += 1

    if total == 0:
        return None
    return round(100 * done / total)


def week_productivity(db: Session, uid: int, monday: date) -> list[dict]:
    """7 дней Пн-Вс начиная с monday: [{date, percent (0-100 или None), is_today}]."""
    today = date.today()
    return [
        {
            "date": monday + timedelta(days=i),
            "percent": day_completion_percent(db, uid, monday + timedelta(days=i)),
            "is_today": (monday + timedelta(days=i)) == today,
        }
        for i in range(7)
    ]
