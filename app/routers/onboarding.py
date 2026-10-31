"""
Онбординг (§7.1): выбор цели → (для fat_loss_safe/muscle_gain — рост/вес/
год рождения и проверка ИМТ+18) → тест уровня → подтверждение расписания →
трейлер сезона → регистрация (app/routers/auth.py) → пролог.

Черновик сезона до регистрации живёт в cookie-сессии (request.session["onboarding"]) —
в БД ничего не попадает, пока человек не создал аккаунт.
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session

from app.auth import get_current_user, require_user
from app.database import get_session
from app.models import User
from app.rendering import render
from app.seasons import engine
from app.seasons_library.loader import get_template, load_library
from app.services.custom_goal import ai_generation_available, generate_custom_template
from app.services.events import log_event_safe
from app.services.flash import push_flash
from app.services.seasons import (
    MAX_ACTIVE_SEASONS,
    create_season,
    get_active_seasons,
    get_or_create_wave,
    wave_composition_count,
)

router = APIRouter(prefix="/onboarding")

HEALTH_CHECK_TEMPLATES = {"fat_loss_safe", "muscle_gain"}
MIN_AGE = 18
MIN_BMI = 18.5


def _draft(request: Request) -> dict:
    return request.session.setdefault("onboarding", {})


@router.get("")
def goal_picker(request: Request, db: Session = Depends(get_session)):
    log_event_safe(db, "onboarding_started")
    tiles = [
        {"id": t.id, "title": t.title, "category": t.category, "lengths": t.lengths}
        for t in load_library().values()
    ]
    tiles.sort(key=lambda t: t["id"])
    return render(
        request,
        "onboarding/goal.html",
        {"tiles": tiles, "ai_available": ai_generation_available()},
    )


@router.post("/goal")
def goal_submit(
    request: Request,
    template_id: str = Form(...),
    custom_text: str = Form(""),
    db: Session = Depends(get_session),
):
    if template_id == "custom":
        template = generate_custom_template(db, custom_text)
        if template is None:
            return render(request, "onboarding/custom_unavailable.html", {"goal_text": custom_text})
        # Сгенерированный шаблон сохранён как draft и используется так же, как
        # библиотечный — здесь просто продолжаем с его id.
        template_id = template.id

    draft = _draft(request)
    draft["template_id"] = template_id
    request.session["onboarding"] = draft

    if template_id in HEALTH_CHECK_TEMPLATES:
        return RedirectResponse("/onboarding/health", status_code=303)
    return RedirectResponse("/onboarding/baseline", status_code=303)


@router.get("/health")
def health_form(request: Request):
    draft = _draft(request)
    if draft.get("template_id") not in HEALTH_CHECK_TEMPLATES:
        return RedirectResponse("/onboarding", status_code=303)
    return render(request, "onboarding/health.html", {"error": None})


@router.post("/health")
def health_submit(
    request: Request,
    height_cm: int = Form(...),
    weight_kg: float = Form(...),
    birth_year: int = Form(...),
):
    draft = _draft(request)
    template_id = draft.get("template_id")
    if template_id not in HEALTH_CHECK_TEMPLATES:
        return RedirectResponse("/onboarding", status_code=303)

    if date.today().year - birth_year < MIN_AGE:
        return render(request, "onboarding/health.html", {"error": "auth.error_age_limit"})

    if template_id == "fat_loss_safe" and not engine.meets_fat_loss_eligibility(weight_kg, height_cm):
        return render(request, "onboarding/bmi_blocked.html", {})

    draft["height_cm"] = height_cm
    draft["weight_kg"] = weight_kg
    draft["birth_year"] = birth_year
    request.session["onboarding"] = draft

    if template_id == "fat_loss_safe":
        # Вес тела — и есть baseline_test этого шаблона, второй раз не спрашиваем.
        draft["baseline_value"] = weight_kg
        request.session["onboarding"] = draft
        return RedirectResponse("/onboarding/schedule", status_code=303)

    return RedirectResponse("/onboarding/baseline", status_code=303)


@router.get("/baseline")
def baseline_form(request: Request):
    draft = _draft(request)
    template_id = draft.get("template_id")
    if not template_id:
        return RedirectResponse("/onboarding", status_code=303)
    template = get_template(template_id)
    return render(request, "onboarding/baseline.html", {"template": template})


@router.post("/baseline")
def baseline_submit(request: Request, value: float = Form(...)):
    draft = _draft(request)
    template_id = draft.get("template_id")
    if not template_id:
        return RedirectResponse("/onboarding", status_code=303)
    template = get_template(template_id)

    if value < template.baseline_test.min or value > template.baseline_test.max:
        return render(
            request,
            "onboarding/baseline.html",
            {"template": template, "error": "onboarding.error_baseline_range"},
        )

    draft["baseline_value"] = value
    if template_id == "muscle_gain":
        draft["secondary_baseline_value"] = draft.get("weight_kg")
    request.session["onboarding"] = draft
    return RedirectResponse("/onboarding/schedule", status_code=303)


@router.get("/schedule")
def schedule_confirm(request: Request):
    draft = _draft(request)
    template_id = draft.get("template_id")
    if not template_id or "baseline_value" not in draft:
        return RedirectResponse("/onboarding", status_code=303)
    template = get_template(template_id)
    return render(request, "onboarding/schedule.html", {"template": template})


@router.post("/schedule")
def schedule_submit(request: Request, length_days: int = Form(...)):
    draft = _draft(request)
    template_id = draft.get("template_id")
    if not template_id:
        return RedirectResponse("/onboarding", status_code=303)
    template = get_template(template_id)
    if length_days not in template.lengths:
        length_days = template.lengths[0]

    draft["length_days"] = length_days
    request.session["onboarding"] = draft
    return RedirectResponse("/onboarding/trailer", status_code=303)


@router.get("/trailer")
def trailer(
    request: Request,
    db: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user),
):
    draft = _draft(request)
    template_id = draft.get("template_id")
    if not template_id or "baseline_value" not in draft or "length_days" not in draft:
        return RedirectResponse("/onboarding", status_code=303)

    template = get_template(template_id)
    today = date.today()
    week_bucket = engine.week_bucket_start(today)
    phase = engine.select_starting_phase(template, draft["baseline_value"])

    # Предварительный просмотр команды — не создаёт волну в БД раньше времени
    wave = get_or_create_wave(db, week_bucket, template_id)
    composition = wave_composition_count(db, wave.id)

    log_event_safe(db, "trailer_shown", meta={"template_id": template_id})

    forecast = engine.forecast_by_plan(
        current_value=draft["baseline_value"],
        remaining_sessions=round(draft["length_days"] / 7 * len(template.schedule.train_days)),
        expected_progress_per_session=phase.days[0].expected_progress,
        adherence=1.0,
    )

    active_count = len(get_active_seasons(db, user.id)) if user else 0

    return render(
        request,
        "onboarding/trailer.html",
        {
            "template": template,
            "length_days": draft["length_days"],
            "composition": composition,
            "forecast": round(forecast, 1),
            "days_per_week": len(template.schedule.train_days),
            "minutes_per_day": template.schedule.minutes[1],
            "user": user,
            "can_start": active_count < MAX_ACTIVE_SEASONS,
            "lang": user.language if user else None,
        },
    )


@router.post("/start")
def start_for_existing_user(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """Старт сезона для уже вошедшего человека (новая цель или следующий
    сезон после Reveal) — минует регистрацию, использует тот же черновик."""
    draft = _draft(request)
    template_id = draft.get("template_id")
    if not template_id or "baseline_value" not in draft or "length_days" not in draft:
        return RedirectResponse("/onboarding", status_code=303)

    if len(get_active_seasons(db, user.id)) >= MAX_ACTIVE_SEASONS:
        push_flash(request, "onboarding.error_too_many_active", "error")
        return RedirectResponse("/seasons", status_code=303)

    season = create_season(
        db,
        uid=user.id,
        template_id=template_id,
        length_days=draft["length_days"],
        baseline_value=draft["baseline_value"],
        reference_date=date.today(),
        secondary_baseline_value=draft.get("secondary_baseline_value"),
    )
    log_event_safe(db, "season_started", uid=user.id, season_id=season.id)
    request.session.pop("onboarding", None)
    request.session["current_season_id"] = season.id
    return RedirectResponse("/today", status_code=303)
