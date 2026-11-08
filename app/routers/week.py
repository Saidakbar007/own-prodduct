"""
«Неделя» (§6, §14): расписание 7 дней, перетаскивание (упрощено — ввод
нового времени вместо drag-and-drop, см. docs/decisions/DECISIONS.md), добавление
обязательного дела/задачи.
"""

import json
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.auth import require_user
from app.database import get_session
from app.models import Commitment, ScheduleBlock, Task, User
from app.rendering import render
from app.services.newlife_onboarding import COMMITMENT_CATEGORIES, WEEKDAY_LABELS
from app.services.schedule_service import get_or_build_schedule_for_day, move_block, sync_schedule_for_day, week_dates
from app.services.usertime import today_for

router = APIRouter()


@router.get("/week")
def week_page(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    today = today_for(user)
    days = week_dates(today)
    day_rows = []
    for d in days:
        blocks = get_or_build_schedule_for_day(db, user, d)
        day_rows.append({"date": d, "is_today": d == today, "blocks": blocks})

    return render(
        request,
        "week.html",
        {
            "day_rows": day_rows,
            "weekday_labels": WEEKDAY_LABELS,
            "categories": COMMITMENT_CATEGORIES,
            "lang": user.language,
        },
    )


@router.post("/week/blocks/{block_id}/move")
def move_block_route(
    block_id: int,
    start_time: str = Form(...),
    end_time: str = Form(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    block = db.get(ScheduleBlock, block_id)
    if block and block.uid == user.id:
        move_block(db, block, start_time, end_time)
    return RedirectResponse("/week", status_code=303)


@router.post("/week/commitments/add")
def add_commitment(
    request: Request,
    title: str = Form(...),
    category: str = Form("other"),
    weekdays: list[int] = Form(default_factory=list),
    start_time: str = Form(...),
    end_time: str = Form(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    if title.strip() and weekdays:
        db.add(
            Commitment(
                uid=user.id,
                title=title.strip(),
                category=category if category in COMMITMENT_CATEGORIES else "other",
                weekdays_json=json.dumps(sorted({w for w in weekdays if 1 <= w <= 7})),
                start_time=start_time,
                end_time=end_time,
            )
        )
        db.commit()
        # §6 п.7: новое дело -> пересчёт расписания недели.
        for d in week_dates(today_for(user)):
            sync_schedule_for_day(db, user, d)
    return RedirectResponse("/week", status_code=303)


@router.post("/week/tasks/add")
def add_task(
    request: Request,
    title: str = Form(...),
    task_date: date = Form(...),
    priority: str = Form("plan"),
    duration_min: int = Form(30),
    start_time: str = Form(""),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    if title.strip():
        db.add(
            Task(
                uid=user.id,
                title=title.strip(),
                task_date=task_date,
                priority=priority if priority in ("do", "plan", "delegate", "drop") else "plan",
                duration_min=duration_min,
                start_time=start_time or None,
                status="planned",
            )
        )
        db.commit()
        sync_schedule_for_day(db, user, task_date)
    return RedirectResponse("/week", status_code=303)
