"""
Паутинка (radar chart) Главной/Прогресса (NEWLIFE_2_0.md §3.1, §3.4):
solid — реальное выполнение за последние 14 дней по сфере (0-10), dashed —
точка А (SphereState.level, выставляется один раз при онбординге и дальше
меняется только явным образом в Профиле → «Мой образ жизни» — то есть
служит неизменным ориентиром "было", а не плывущим средним).

Формула "реального выполнения" для сферы: доля выполненных (done/minimal/
rescued) дней активных сезонов этой сферы + выполненных привычек,
отмеченных этой сферой, за последние 14 дней, из тех, что были
запланированы в эти дни — same unit idea as app/services/productivity.py,
но на 14 дней и per-sphere, а не на 1 день и по всем сферам сразу.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

from sqlmodel import Session, select

from app.models import Habit, HabitLog, Season, SeasonDay, SphereState
from app.newlife.goal_catalog import goal_meta

WINDOW_DAYS = 14


def _sphere_of_season(season: Season) -> str | None:
    if season.sphere_id:
        return season.sphere_id
    entry = goal_meta(season.template_id)
    return entry.sphere if entry else None


def sphere_recent_score(db: Session, uid: int, sphere_id: str, today: date) -> int:
    """0-10: доля выполненного за последние 14 дней в этой сфере. Без
    запланированного (ни сезонов, ни привычек этой сферы) — 0, не None:
    радар всегда рисует все выбранные сферы, пустая сфера = просела, это
    и есть сигнал "не видно активности"."""
    since = today - timedelta(days=WINDOW_DAYS - 1)
    total = 0
    done = 0

    seasons = db.exec(select(Season).where(Season.uid == uid)).all()
    sphere_season_ids = [s.id for s in seasons if _sphere_of_season(s) == sphere_id]
    if sphere_season_ids:
        days = db.exec(
            select(SeasonDay).where(
                SeasonDay.season_id.in_(sphere_season_ids),
                SeasonDay.calendar_date >= since,
                SeasonDay.calendar_date <= today,
                SeasonDay.kind != "rest",
            )
        ).all()
        total += len(days)
        done += sum(1 for d in days if d.status in ("done", "minimal", "rescued"))

    habits = db.exec(select(Habit).where(Habit.uid == uid, Habit.active.is_(True))).all()
    sphere_habits = [h for h in habits if sphere_id in json.loads(h.spheres_json)]
    if sphere_habits:
        logs = db.exec(
            select(HabitLog).where(
                HabitLog.habit_id.in_([h.id for h in sphere_habits]),
                HabitLog.log_date >= since,
                HabitLog.log_date <= today,
            )
        ).all()
        log_by_key = {(log.habit_id, log.log_date): log.status for log in logs}
        for h in sphere_habits:
            due_days = json.loads(h.days_json)
            for i in range(WINDOW_DAYS):
                d = since + timedelta(days=i)
                if d.isoweekday() not in due_days:
                    continue
                total += 1
                if log_by_key.get((h.id, d)) in ("done", "minimal"):
                    done += 1

    if total == 0:
        return 0
    return round(10 * done / total)


def sphere_radar_values(db: Session, uid: int, today: date) -> list[dict]:
    """[{sphere_id, baseline, current}] для всех сфер пользователя
    (SphereState существует), отсортировано как в app/newlife/spheres.py."""
    from app.newlife.spheres import SPHERE_IDS

    states = {s.sphere_id: s for s in db.exec(select(SphereState).where(SphereState.uid == uid)).all()}
    out = []
    for sphere_id in SPHERE_IDS:
        state = states.get(sphere_id)
        if state is None:
            continue
        out.append(
            {
                "sphere_id": sphere_id,
                "baseline": state.level,
                "current": sphere_recent_score(db, uid, sphere_id, today),
                "active": state.active,
            }
        )
    return out
