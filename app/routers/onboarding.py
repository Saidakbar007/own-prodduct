"""
Онбординг NewLife v8 (§5 docs/specs/NEWLIFE_V8_SPEC.md): философия → сферы → уровень
по сфере → цель (для "Тела" — каталог Сезонов, §7.1 старого ТЗ: рост/вес/
год рождения для fat_loss_safe/muscle_gain, тест уровня) → режим дня →
обязательные дела → время на себя → когда больше сил → ограничения → WOOP →
длина сезона → раскрытие (колесо жизни + цель + расписание) → регистрация
(app/routers/auth.py) → первое действие → тур.

Черновик до регистрации живёт в cookie-сессии (request.session["onboarding"]) —
в БД ничего не попадает, пока человек не создал аккаунт. Уже зарегистрированный
человек с заполненной точкой А (Profile.onboarding_done_at) пропускает экраны
1-3/6-11 и сразу попадает в каталог целей — это и есть "следующий сезон"/
"начать новый сезон".
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.auth import get_current_user, require_user
from app.database import get_session
from app.models import Profile, SphereState, User
from app.newlife import point_a
from app.newlife.goal_catalog import goal_meta
from app.newlife.spheres import SPHERES, SPHERE_BY_ID
from app.rendering import render
from app.seasons import engine
from app.seasons_library.loader import get_template, load_library
from app.services.events import log_event_safe
from app.services.flash import push_flash
from app.services.newlife_onboarding import (
    CHRONOTYPE_OPTIONS,
    COMMITMENT_CATEGORIES,
    CONSTRAINT_OPTIONS,
    DAILY_MINUTES_OPTIONS,
    OBSTACLE_OPTIONS,
    WAKE_TIME_OPTIONS,
    SLEEP_TIME_OPTIONS,
    WEEKDAY_LABELS,
    WOOP_PLANS,
    has_completed_profile,
)
from app.services.seasons import (
    MAX_ACTIVE_SEASONS,
    create_season,
    get_active_seasons,
    get_or_create_wave,
    wave_composition_count,
)
from app.services.usertime import today_for

router = APIRouter(prefix="/onboarding")

HEALTH_CHECK_TEMPLATES = {"fat_loss_safe", "muscle_gain"}
MIN_AGE = 18
MIN_BMI = 18.5
MIN_SPHERES = 1
MAX_SPHERES = 3


def _draft(request: Request) -> dict:
    return request.session.setdefault("onboarding", {})


def _save(request: Request, draft: dict) -> None:
    request.session["onboarding"] = draft


@router.get("")
def philosophy(request: Request, db: Session = Depends(get_session), user: Optional[User] = Depends(get_current_user)):
    """Экран 1: философия продукта. Уже знакомому человеку с заполненной
    точкой А — сразу в каталог целей (новая цель/следующий сезон)."""
    if user:
        profile = db.exec(select(Profile).where(Profile.uid == user.id)).first()
        if has_completed_profile(profile):
            return RedirectResponse("/onboarding/goal", status_code=303)
    log_event_safe(db, "onboarding_started")
    request.session["onboarding"] = {}
    return render(request, "onboarding/philosophy.html", {"lang": user.language if user else None})


@router.get("/spheres")
def spheres_form(request: Request):
    """Экран 2: какие 1-3 сферы хочешь менять в первую очередь."""
    draft = _draft(request)
    return render(
        request,
        "onboarding/spheres.html",
        {"spheres": SPHERES, "selected": draft.get("spheres", [])},
    )


@router.post("/spheres")
def spheres_submit(request: Request, sphere_ids: list[str] = Form(default_factory=list)):
    draft = _draft(request)
    chosen = [s for s in sphere_ids if s in SPHERE_BY_ID][:MAX_SPHERES]
    if not chosen:
        chosen = ["body"]  # кнопка "пропустить" — безопасное значение по умолчанию
    draft["spheres"] = chosen
    draft["sphere_level_idx"] = 0
    draft["sphere_levels"] = {}
    _save(request, draft)
    return RedirectResponse("/onboarding/sphere-level", status_code=303)


@router.get("/sphere-level")
def sphere_level_form(request: Request):
    """Экран 3: один вопрос уровня на каждую выбранную сферу, по очереди."""
    draft = _draft(request)
    spheres = draft.get("spheres") or []
    idx = draft.get("sphere_level_idx", 0)
    if idx >= len(spheres):
        return RedirectResponse("/onboarding/goal", status_code=303)
    sphere_id = spheres[idx]
    question = point_a.question_for(sphere_id)
    return render(
        request,
        "onboarding/sphere_level.html",
        {
            "sphere": SPHERE_BY_ID[sphere_id],
            "question": question,
            "step": idx + 1,
            "total": len(spheres),
        },
    )


@router.post("/sphere-level")
def sphere_level_submit(request: Request, option_index: Optional[int] = Form(None)):
    draft = _draft(request)
    spheres = draft.get("spheres") or []
    idx = draft.get("sphere_level_idx", 0)
    if idx < len(spheres):
        sphere_id = spheres[idx]
        level = point_a.level_for_answer(sphere_id, option_index) if option_index is not None else None
        levels = draft.get("sphere_levels", {})
        levels[sphere_id] = level if level is not None else 4  # пропуск -> безопасное среднее
        draft["sphere_levels"] = levels
    draft["sphere_level_idx"] = idx + 1
    _save(request, draft)
    return RedirectResponse("/onboarding/sphere-level", status_code=303)


@router.get("/goal")
def goal_picker(request: Request, db: Session = Depends(get_session)):
    """Экран 4: карточки целей из каталога выбранных на экране 2 сфер (PRD
    1.0 F2 — любая из 11, не только "Тело"). Без выбранных сфер в черновике
    (человек уже зарегистрирован и зашёл сюда за новой целью/сезоном,
    см. docstring модуля) — показываем каталог всех сфер без фильтра."""
    draft = _draft(request)
    chosen_spheres = draft.get("spheres") or []

    tiles = []
    for t in load_library().values():
        entry = goal_meta(t.id)
        if entry is None:
            continue
        if chosen_spheres and entry.sphere not in chosen_spheres:
            continue
        tiles.append(
            {
                "id": t.id,
                "title": entry.title.ru,
                "sphere": entry.sphere,
                "lengths": t.lengths,
            }
        )

    sphere_order = {s: i for i, s in enumerate(chosen_spheres)}
    tiles.sort(key=lambda tile: (sphere_order.get(tile["sphere"], 99), tile["id"]))

    spheres_shown = sorted({tile["sphere"] for tile in tiles}, key=lambda s: sphere_order.get(s, 99))

    return render(
        request,
        "onboarding/goal.html",
        {
            "tiles": tiles,
            "spheres_shown": [SPHERE_BY_ID[s] for s in spheres_shown],
        },
    )


@router.post("/goal/skip")
def goal_skip(request: Request):
    """«Пропустить» (PRD 1.0 §5: кнопка-пропуск есть на каждом экране) —
    без выбора цели сейчас; привычку/цель в любую сферу можно завести позже
    из «Сезонов»."""
    draft = _draft(request)
    draft.pop("template_id", None)
    _save(request, draft)
    return RedirectResponse("/onboarding/mode", status_code=303)


@router.post("/goal")
def goal_submit(
    request: Request,
    template_id: str = Form(...),
    db: Session = Depends(get_session),
):
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
        return RedirectResponse("/onboarding/goal", status_code=303)
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
        return RedirectResponse("/onboarding/goal", status_code=303)

    if date.today().year - birth_year < MIN_AGE:
        return render(request, "onboarding/health.html", {"error": "auth.error_age_limit"})

    if template_id == "fat_loss_safe":
        # Ориентировочный целевой вес до клампа темпа (длительность сезона
        # выбирается позже, на /onboarding/schedule) — PRD 1.0: блокировать
        # при текущем ИЛИ целевом ИМТ < 18,5, не только текущем.
        nominal_target = weight_kg - get_template(template_id).target_default
        if not engine.meets_fat_loss_eligibility(weight_kg, height_cm, nominal_target):
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

    if template_id == "muscle_gain":
        # v8 §7: вес тела — главная метрика (уже спросили здесь), баланс —
        # на шаге /onboarding/baseline спросим вспомогательный рабочий вес.
        draft["baseline_value"] = weight_kg
        request.session["onboarding"] = draft
        return RedirectResponse("/onboarding/baseline", status_code=303)

    return RedirectResponse("/onboarding/baseline", status_code=303)


@router.get("/baseline")
def baseline_form(request: Request):
    draft = _draft(request)
    template_id = draft.get("template_id")
    if not template_id:
        return RedirectResponse("/onboarding/goal", status_code=303)
    template = get_template(template_id)
    return render(request, "onboarding/baseline.html", {"template": template})


@router.post("/baseline")
def baseline_submit(request: Request, value: float = Form(...)):
    draft = _draft(request)
    template_id = draft.get("template_id")
    if not template_id:
        return RedirectResponse("/onboarding/goal", status_code=303)
    template = get_template(template_id)

    if value < template.baseline_test.min or value > template.baseline_test.max:
        return render(
            request,
            "onboarding/baseline.html",
            {"template": template, "error": "onboarding.error_baseline_range"},
        )

    if template_id == "muscle_gain":
        # v8 §7: это вопрос про вспомогательный рабочий вес в приседе —
        # baseline_value (вес тела) уже выставлен на шаге /onboarding/health.
        draft["secondary_baseline_value"] = value
    else:
        draft["baseline_value"] = value
    request.session["onboarding"] = draft
    return RedirectResponse("/onboarding/schedule", status_code=303)


@router.get("/schedule")
def schedule_confirm(request: Request):
    draft = _draft(request)
    template_id = draft.get("template_id")
    if not template_id or "baseline_value" not in draft:
        return RedirectResponse("/onboarding/goal", status_code=303)
    template = get_template(template_id)
    return render(request, "onboarding/schedule.html", {"template": template})


@router.post("/schedule")
def schedule_submit(request: Request, length_days: int = Form(...)):
    draft = _draft(request)
    template_id = draft.get("template_id")
    if not template_id:
        return RedirectResponse("/onboarding/goal", status_code=303)
    template = get_template(template_id)
    if length_days not in template.lengths:
        length_days = template.lengths[0]

    draft["length_days"] = length_days
    request.session["onboarding"] = draft
    return RedirectResponse("/onboarding/mode", status_code=303)


# --------------------------------------------------------- экран 6: режим дня

@router.get("/mode")
def mode_form(request: Request):
    draft = _draft(request)
    return render(
        request,
        "onboarding/mode.html",
        {
            "wake_options": WAKE_TIME_OPTIONS,
            "sleep_options": SLEEP_TIME_OPTIONS,
            "wake_selected": draft.get("wake_time", "07:00"),
            "sleep_selected": draft.get("sleep_time", "23:00"),
        },
    )


@router.post("/mode")
def mode_submit(
    request: Request,
    wake_time: str = Form("07:00"),
    sleep_time: str = Form("23:00"),
):
    draft = _draft(request)
    draft["wake_time"] = wake_time if wake_time in WAKE_TIME_OPTIONS else "07:00"
    draft["sleep_time"] = sleep_time if sleep_time in SLEEP_TIME_OPTIONS else "23:00"
    _save(request, draft)
    return RedirectResponse("/onboarding/commitments", status_code=303)


# ------------------------------------------------- экран 7: обязательные дела

@router.get("/commitments")
def commitments_form(request: Request):
    draft = _draft(request)
    return render(
        request,
        "onboarding/commitments.html",
        {
            "categories": COMMITMENT_CATEGORIES,
            "weekday_labels": WEEKDAY_LABELS,
            "commitments": draft.get("commitments", []),
        },
    )


@router.post("/commitments")
def commitments_submit(
    request: Request,
    title: str = Form(""),
    category: str = Form("other"),
    weekdays: list[int] = Form(default_factory=list),
    start_time: str = Form(""),
    end_time: str = Form(""),
    commute_minutes: int = Form(0),
    action: str = Form("next"),
):
    draft = _draft(request)
    commitments = draft.get("commitments", [])

    if action == "add" and title.strip() and weekdays and start_time and end_time:
        commitments.append(
            {
                "title": title.strip(),
                "category": category if category in COMMITMENT_CATEGORIES else "other",
                "weekdays": sorted({d for d in weekdays if 1 <= d <= 7}),
                "start_time": start_time,
                "end_time": end_time,
            }
        )
        draft["commitments"] = commitments
        _save(request, draft)
        return RedirectResponse("/onboarding/commitments", status_code=303)

    draft["commute_minutes"] = commute_minutes if commute_minutes in (0, 30, 60, 90) else 0
    _save(request, draft)
    return RedirectResponse("/onboarding/daily-minutes", status_code=303)


@router.post("/commitments/remove")
def commitments_remove(request: Request, index: int = Form(...)):
    draft = _draft(request)
    commitments = draft.get("commitments", [])
    if 0 <= index < len(commitments):
        commitments.pop(index)
    draft["commitments"] = commitments
    _save(request, draft)
    return RedirectResponse("/onboarding/commitments", status_code=303)


# ------------------------------------------- экран 8: сколько времени в день

@router.get("/daily-minutes")
def daily_minutes_form(request: Request):
    draft = _draft(request)
    return render(
        request,
        "onboarding/daily_minutes.html",
        {"options": DAILY_MINUTES_OPTIONS, "selected": draft.get("daily_minutes", 30)},
    )


@router.post("/daily-minutes")
def daily_minutes_submit(request: Request, daily_minutes: int = Form(30)):
    draft = _draft(request)
    draft["daily_minutes"] = daily_minutes if daily_minutes in DAILY_MINUTES_OPTIONS else 30
    _save(request, draft)
    return RedirectResponse("/onboarding/chronotype", status_code=303)


# --------------------------------------------- экран 9: когда больше сил

@router.get("/chronotype")
def chronotype_form(request: Request):
    draft = _draft(request)
    return render(
        request,
        "onboarding/chronotype.html",
        {"options": CHRONOTYPE_OPTIONS, "selected": draft.get("chronotype", "varies")},
    )


@router.post("/chronotype")
def chronotype_submit(request: Request, chronotype: str = Form("varies")):
    draft = _draft(request)
    draft["chronotype"] = chronotype if chronotype in CHRONOTYPE_OPTIONS else "varies"
    _save(request, draft)
    return RedirectResponse("/onboarding/constraints", status_code=303)


# ------------------------------------------------------ экран 10: ограничения

@router.get("/constraints")
def constraints_form(request: Request):
    draft = _draft(request)
    return render(
        request,
        "onboarding/constraints.html",
        {"options": CONSTRAINT_OPTIONS, "selected": draft.get("constraints", [])},
    )


@router.post("/constraints")
def constraints_submit(request: Request, constraints: list[str] = Form(default_factory=list)):
    draft = _draft(request)
    draft["constraints"] = [c for c in constraints if c in CONSTRAINT_OPTIONS]
    _save(request, draft)
    return RedirectResponse("/onboarding/woop", status_code=303)


# --------------------------------------------------------------- экран 11: WOOP

@router.get("/woop")
def woop_form(request: Request):
    draft = _draft(request)
    obstacle = draft.get("main_obstacle")
    plan_options = WOOP_PLANS.get(obstacle, []) if obstacle else []
    return render(
        request,
        "onboarding/woop.html",
        {"obstacle_options": OBSTACLE_OPTIONS, "obstacle": obstacle, "plan_options": plan_options},
    )


@router.post("/woop/obstacle")
def woop_obstacle_submit(request: Request, main_obstacle: str = Form(...)):
    draft = _draft(request)
    draft["main_obstacle"] = main_obstacle if main_obstacle in OBSTACLE_OPTIONS else None
    _save(request, draft)
    return RedirectResponse("/onboarding/woop", status_code=303)


@router.post("/woop")
def woop_submit(request: Request, plan: Optional[str] = Form(None)):
    draft = _draft(request)
    draft["woop_plan"] = plan
    _save(request, draft)
    return RedirectResponse("/onboarding/trailer", status_code=303)


# --------------------------------------------------- экран 12: раскрытие

@router.get("/trailer")
def trailer(
    request: Request,
    db: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user),
):
    draft = _draft(request)
    template_id = draft.get("template_id")
    has_goal = template_id and "baseline_value" in draft and "length_days" in draft

    goal_ctx: dict = {}
    if has_goal:
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
        goal_ctx = {
            "template": template,
            "length_days": draft["length_days"],
            "composition": composition,
            "forecast": round(forecast, 1),
            "days_per_week": len(template.schedule.train_days),
            "minutes_per_day": template.schedule.minutes[1],
        }

    active_count = len(get_active_seasons(db, user.id)) if user else 0
    sphere_levels = {
        SPHERE_BY_ID[sid]: lvl for sid, lvl in draft.get("sphere_levels", {}).items() if sid in SPHERE_BY_ID
    }

    return render(
        request,
        "onboarding/trailer.html",
        {
            "has_goal": bool(has_goal),
            "sphere_levels": sphere_levels,
            "commitments": draft.get("commitments", []),
            "wake_time": draft.get("wake_time"),
            "sleep_time": draft.get("sleep_time"),
            "user": user,
            "can_start": active_count < MAX_ACTIVE_SEASONS,
            "lang": user.language if user else None,
            **goal_ctx,
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

    entry = goal_meta(template_id)
    season = create_season(
        db,
        uid=user.id,
        template_id=template_id,
        length_days=draft["length_days"],
        baseline_value=draft["baseline_value"],
        reference_date=today_for(user),  # не date.today() — см. auth.py register_submit
        secondary_baseline_value=draft.get("secondary_baseline_value"),
        sphere_id=entry.sphere if entry else None,
    )
    log_event_safe(db, "season_started", uid=user.id, season_id=season.id)
    request.session.pop("onboarding", None)
    request.session["current_season_id"] = season.id
    return RedirectResponse("/today", status_code=303)
