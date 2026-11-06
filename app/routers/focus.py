"""
Таймер фокуса/практики (PRD 1.0 F3/F4): полноэкранный таймер для целей,
у которых metric.kind == "timer" в каталоге сферы (глубокий фокус, дыхание,
время на природе, осознанность и т.п., см. app/newlife/goal_catalog.py).

Блок длительностью N минут отсчитывается в браузере (static/focus_timer.js).
«Отвлёкся» обнуляет прогресс текущего блока — его нужно начать заново, а не
засчитывать частично (осознанное решение: метод работает только на полных
блоках без отвлечений, см. docs/decisions/DECISIONS.md). Завершённый блок
отмечает сегодняшний день сезона сделанным и пишет минуты в
SeasonDay.logged_minutes — они суммируются в /measure
(app.services.seasons.sum_logged_minutes_since_last_measure), так что
недельный замер этих целей не нужно вспоминать и вводить вручную с нуля.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session

from app.auth import require_user
from app.database import get_session
from app.models import User
from app.rendering import render
from app.services import mascot
from app.services.events import log_event_safe
from app.services.flash import push_flash
from app.services.seasons import (
    ensure_days_built_for_today,
    get_current_season,
    get_day,
    goal_metric_for_season,
    sync_season_state,
    today_day_number,
)
from app.services.usertime import today_for

router = APIRouter()

BLOCK_MINUTES = (5, 10, 15, 25, 50)


def _today_train_day(request: Request, user: User, db: Session):
    season = get_current_season(db, user.id, request)
    if not season:
        return None, None
    today = today_for(user)
    ensure_days_built_for_today(db, season, today)
    season = sync_season_state(db, season, today)
    day = get_day(db, season.id, today_day_number(season, today))
    return season, day


@router.get("/focus")
def focus_picker(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    season, day = _today_train_day(request, user, db)
    if not season:
        return RedirectResponse("/today", status_code=303)
    metric = goal_metric_for_season(season)
    if not metric or metric.kind != "timer":
        return RedirectResponse("/today", status_code=303)
    if not day or day.status != "planned" or day.kind == "measure":
        return RedirectResponse("/today", status_code=303)

    return render(
        request,
        "focus.html",
        {
            "season": season,
            "day": day,
            "block_minutes": BLOCK_MINUTES,
            "metric_unit": metric.unit,
            "lang": user.language,
        },
    )


@router.post("/focus/complete")
def focus_complete(
    request: Request,
    minutes: float = Form(...),
    minimal: bool = Form(False),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    season, day = _today_train_day(request, user, db)
    if not season or not day or day.status != "planned":
        return RedirectResponse("/today", status_code=303)

    day.status = "minimal" if minimal else "done"
    day.done_at = datetime.now(timezone.utc)
    day.logged_minutes = max(0.0, minutes)
    db.add(day)
    db.commit()

    event = "day_minimal" if minimal else "day_done"
    log_event_safe(db, event, uid=user.id, season_id=season.id)
    push_flash(request, mascot.phrase_for("minimal" if minimal else "done", user.language), "success")
    return RedirectResponse("/today", status_code=303)
