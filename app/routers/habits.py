"""
«Привычки» (§10, §14 NEWLIFE_V8_SPEC.md): полезные и плохие привычки —
список (сегодня/неделя/серия), каталог на ~40 штук + своя, лог в один тап.
"""

import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.auth import require_user
from app.database import get_session
from app.models import BadHabit, Habit, User
from app.newlife.habit_catalog import (
    bad_habit_item_by_id,
    habit_item_by_id,
    load_bad_habit_catalog,
    load_habit_catalog,
)
from app.newlife.spheres import SPHERE_BY_ID, SPHERES
from app.rendering import render
from app.services.habits import (
    bad_habit_recent_average,
    habit_streak,
    log_bad_habit_slip,
    log_habit,
    most_common_trigger,
    week_completion_rate,
)
from app.services.schedule_service import week_dates
from app.services.usertime import today_for

router = APIRouter()

ALL_WEEKDAYS = list(range(1, 8))


@router.get("/habits")
def habits_page(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    today = today_for(user)
    monday = week_dates(today)[0]

    habits = db.exec(select(Habit).where(Habit.uid == user.id, Habit.active.is_(True))).all()
    habit_rows = []
    for h in habits:
        days = json.loads(h.days_json)
        habit_rows.append(
            {
                "habit": h,
                "due_today": today.isoweekday() in days,
                "today_status": None,
                "streak": habit_streak(db, h, today),
                "week_rate": round(week_completion_rate(db, h, monday) * 100),
            }
        )
        from app.services.habits import habit_logs_by_date

        logs = habit_logs_by_date(db, h.id)
        habit_rows[-1]["today_status"] = logs.get(today)

    bad_habits = db.exec(select(BadHabit).where(BadHabit.uid == user.id, BadHabit.active.is_(True))).all()
    bad_rows = []
    for bh in bad_habits:
        avg = bad_habit_recent_average(db, bh.id, today)
        bad_rows.append(
            {
                "bad_habit": bh,
                "avg_per_day": round(avg, 1) if avg is not None else None,
                "common_trigger": most_common_trigger(db, bh.id),
            }
        )

    return render(
        request,
        "habits.html",
        {"habit_rows": habit_rows, "bad_rows": bad_rows, "lang": user.language},
    )


@router.post("/habits/{habit_id}/log")
def log_habit_route(
    habit_id: int, status: str = Form(...), user: User = Depends(require_user), db: Session = Depends(get_session)
):
    habit = db.get(Habit, habit_id)
    if habit and habit.uid == user.id and status in ("done", "minimal"):
        today = today_for(user)
        log_habit(db, habit.id, today, status, datetime.now(timezone.utc))
    return RedirectResponse("/habits", status_code=303)


@router.post("/habits/{habit_id}/deactivate")
def deactivate_habit(habit_id: int, user: User = Depends(require_user), db: Session = Depends(get_session)):
    habit = db.get(Habit, habit_id)
    if habit and habit.uid == user.id:
        habit.active = False
        db.add(habit)
        db.commit()
    return RedirectResponse("/habits", status_code=303)


@router.get("/habits/add")
def add_habit_form(request: Request, user: User = Depends(require_user)):
    catalog = load_habit_catalog()
    by_sphere: dict[str, list] = {s.id: [] for s in SPHERES}
    for item in catalog:
        for sphere_id in item.spheres:
            by_sphere.setdefault(sphere_id, []).append(item)
    return render(
        request,
        "habit_add.html",
        {"spheres": SPHERES, "by_sphere": by_sphere, "lang": user.language},
    )


@router.post("/habits/add")
def add_habit_submit(
    request: Request,
    catalog_id: str = Form(""),
    custom_title: str = Form(""),
    time_pref: str = Form("exact"),
    exact_time: str = Form(""),
    days: list[int] = Form(default_factory=lambda: ALL_WEEKDAYS),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    item = habit_item_by_id(catalog_id) if catalog_id else None
    if item:
        title = item.title
        duration = item.duration_min
        minimal = item.minimal
        spheres = item.spheres
        pref = time_pref if time_pref in ("morning", "day", "evening", "exact") else item.time_pref
    elif custom_title.strip():
        title = custom_title.strip()
        duration = 10
        minimal = "2 минуты"  # §9 "правило двух минут" — минимальная версия всегда есть
        spheres = []
        pref = time_pref if time_pref in ("morning", "day", "evening", "exact") else "exact"
    else:
        return RedirectResponse("/habits/add", status_code=303)

    habit = Habit(
        uid=user.id,
        catalog_id=catalog_id or None,
        title=title,
        spheres_json=json.dumps(spheres),
        days_json=json.dumps(sorted(set(days)) or ALL_WEEKDAYS),
        time_pref=pref,
        exact_time=exact_time or None,
        duration_min=duration,
        minimal_version=minimal,
    )
    db.add(habit)
    db.commit()
    return RedirectResponse("/habits", status_code=303)


@router.get("/habits/bad/add")
def add_bad_habit_form(request: Request, user: User = Depends(require_user)):
    triggers, catalog = load_bad_habit_catalog()
    return render(
        request,
        "bad_habit_add.html",
        {"catalog": catalog, "triggers": triggers, "lang": user.language},
    )


@router.post("/habits/bad/add")
def add_bad_habit_submit(
    request: Request,
    catalog_id: str = Form(""),
    custom_title: str = Form(""),
    triggers: list[str] = Form(default_factory=list),
    baseline_per_day: float = Form(1),
    unit: str = Form("times"),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    item = bad_habit_item_by_id(catalog_id) if catalog_id else None
    title = item.title if item else custom_title.strip()
    if not title:
        return RedirectResponse("/habits/bad/add", status_code=303)

    final_unit = item.unit if item else (unit if unit in ("times", "minutes") else "times")
    # §10: постепенная цель — минус 10–20% от базовой частоты за 2 недели.
    target = max(0.0, baseline_per_day * 0.85)

    bad_habit = BadHabit(
        uid=user.id,
        catalog_id=catalog_id or None,
        title=title,
        triggers_json=json.dumps(triggers or (item.triggers if item else [])),
        replacement_id=item.replacement_id if item else None,
        baseline_per_day=baseline_per_day,
        target_per_day=target,
        unit=final_unit,
    )
    db.add(bad_habit)
    db.commit()
    return RedirectResponse("/habits", status_code=303)


@router.post("/habits/bad/{bad_habit_id}/slip")
def log_slip(
    bad_habit_id: int,
    trigger_id: Optional[str] = Form(None),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    bad_habit = db.get(BadHabit, bad_habit_id)
    if bad_habit and bad_habit.uid == user.id:
        today = today_for(user)
        log_bad_habit_slip(db, bad_habit.id, today, trigger_id or None, datetime.now(timezone.utc))
    return RedirectResponse("/habits", status_code=303)


@router.post("/habits/bad/{bad_habit_id}/deactivate")
def deactivate_bad_habit(bad_habit_id: int, user: User = Depends(require_user), db: Session = Depends(get_session)):
    bad_habit = db.get(BadHabit, bad_habit_id)
    if bad_habit and bad_habit.uid == user.id:
        bad_habit.active = False
        db.add(bad_habit)
        db.commit()
    return RedirectResponse("/habits", status_code=303)
