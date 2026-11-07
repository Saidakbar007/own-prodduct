"""
Программа тренировки (доп. задача, см. docs/decisions/DECISIONS.md →
«Этап "Доделай" + guide + wger»): для дней тренировки целей из
WORKOUT_PROGRAM_GOALS (muscle_gain, fat_loss_safe) «Сегодня» ведёт сюда —
список упражнений программы (зал/дом) с картинкой/техникой и полями
вес/повторы. Отметка дня сделанным — через уже существующие /today/done и
/today/minimal (эта страница их не дублирует, только лог по упражнениям).
"""

import json

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session

from app.auth import require_user
from app.database import get_session
from app.models import User
from app.newlife.exercise_catalog import exercise_meta
from app.newlife.workout_programs import program_for_goal
from app.rendering import render
from app.services.seasons import (
    ensure_days_built_for_today,
    get_current_season,
    get_day,
    sync_season_state,
    today_day_number,
)
from app.services.usertime import today_for

router = APIRouter()

_EQUIPMENT_SESSION_KEY = "workout_equipment"


def _today_workout_day(request: Request, user: User, db: Session):
    season = get_current_season(db, user.id, request)
    if not season:
        return None, None
    today = today_for(user)
    ensure_days_built_for_today(db, season, today)
    season = sync_season_state(db, season, today)
    day = get_day(db, season.id, today_day_number(season, today))
    return season, day


def _workout_log(day) -> dict:
    if not day or not day.workout_log:
        return {}
    try:
        entries = json.loads(day.workout_log)
    except (ValueError, TypeError):
        return {}
    return {e["exercise_id"]: e for e in entries if "exercise_id" in e}


@router.get("/workout")
def workout_page(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    season, day = _today_workout_day(request, user, db)
    if not season or not day or day.kind == "measure" or day.status != "planned":
        return RedirectResponse("/today", status_code=303)

    equipment = request.session.get(_EQUIPMENT_SESSION_KEY, "gym")
    program = program_for_goal(season.template_id, equipment)
    if not program:
        return RedirectResponse("/today", status_code=303)

    logged = _workout_log(day)
    exercises = []
    for exercise_id in program.exercises:
        entry = exercise_meta(exercise_id)
        if not entry:
            continue
        logged_set = logged.get(exercise_id, {})
        exercises.append(
            {
                "id": exercise_id,
                "name": entry.name.text(user.language),
                "muscles": entry.muscles,
                "technique": entry.technique.text(user.language),
                "easy_version": entry.easy_version.text(user.language),
                "hard_version": entry.hard_version.text(user.language),
                "weight_kg": logged_set.get("weight_kg"),
                "reps": logged_set.get("reps"),
            }
        )

    return render(
        request,
        "workout.html",
        {
            "season": season,
            "day": day,
            "program": program,
            "program_title": program.title.text(user.language),
            "progression": program.progression.text(user.language),
            "equipment": equipment,
            "exercises": exercises,
            "lang": user.language,
        },
    )


@router.post("/workout/equipment")
def set_equipment(
    request: Request,
    equipment: str = Form(...),
    user: User = Depends(require_user),
):
    if equipment in ("gym", "home"):
        request.session[_EQUIPMENT_SESSION_KEY] = equipment
    return RedirectResponse("/workout", status_code=303)


@router.post("/workout/log")
def log_exercise(
    request: Request,
    exercise_id: str = Form(...),
    weight_kg: str = Form(""),
    reps: str = Form(""),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    season, day = _today_workout_day(request, user, db)
    if not season or not day or day.status != "planned":
        return RedirectResponse("/today", status_code=303)

    logged = _workout_log(day)
    logged[exercise_id] = {
        "exercise_id": exercise_id,
        "weight_kg": float(weight_kg) if weight_kg.strip() else None,
        "reps": int(float(reps)) if reps.strip() else None,
    }
    day.workout_log = json.dumps(list(logged.values()))
    db.add(day)
    db.commit()
    return RedirectResponse("/workout", status_code=303)
