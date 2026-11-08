"""
«Сегодня» (§14 NEWLIFE_v8 / §7.2 Сезонов): чек-ин энергии/стресса/настроения,
главное действие дня (сезон, если есть), лента дня по времени (расписание),
ведущий. Единственный экран, который реально нужен каждый день. Сезон теперь
необязателен — "Сегодня" работает и для человека без активной цели (только
привычки/расписание), обязателен лишь заполненный профиль (точка А).
"""

import json
import math
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.auth import require_user
from app.database import get_session
from app.models import BadHabit, Habit, HabitLog, Profile, Proof, Season, SeasonDay, SphereState, User
from app.newlife import methods as methods_catalog
from app.newlife.goal_catalog import first_guide_step, goal_meta
from app.newlife.spheres import SPHERE_BY_ID, SPHERES
from app.newlife.workout_programs import WORKOUT_PROGRAM_GOALS
from app.rendering import render
from app.seasons import engine
from app.services import mascot
from app.services.checkin_service import (
    get_checkin,
    is_in_recovery_mode,
    log_checkin,
    should_offer_recovery_mode,
    start_recovery_mode,
)
from app.services.day_questions import record_answer, todays_question
from app.services.events import log_event_safe
from app.services.flash import push_flash
from app.services.habits import clean_duration, habit_logs_by_date, habit_streak
from app.services.newlife_onboarding import WEEKDAY_LABELS, has_completed_profile
from app.newlife.scheduler import parse_hhmm
from app.services.productivity import week_productivity
from app.services.progress import sphere_radar_values
from app.services.schedule_service import get_or_build_schedule_for_day, week_dates
from app.services.seasons import (
    compute_forecast,
    ensure_days_built_for_today,
    get_active_seasons,
    get_current_season,
    get_day,
    goal_metric_for_season,
    set_current_season,
    sync_season_state,
    today_day_number,
)
from app.services.trust import PENALTY_BLURRY_OR_BLANK_PHOTO, apply_trust_penalty
from app.services.uploads import analyze_photo, save_photo_bytes
from app.services.usertime import now_for, today_for

router = APIRouter()

RING_RADIUS = 36
RING_CIRCUMFERENCE = 2 * math.pi * RING_RADIUS


def _prepare_season(request: Request, user: User, db: Session) -> Optional[Season]:
    season = get_current_season(db, user.id, request)
    if not season:
        return None
    today = today_for(user)
    ensure_days_built_for_today(db, season, today)
    season = sync_season_state(db, season, today)
    return season


def _wave_today_checkins(db: Session, season: Season, today: date) -> int:
    """Сколько участников волны уже отметились сегодня (без личных данных —
    полноценный «Состав» со скрином людей будет в Фазе 3)."""
    season_ids = db.exec(select(Season.id).where(Season.wave_id == season.wave_id)).all()
    if not season_ids:
        return 0
    done_today = db.exec(
        select(SeasonDay.season_id)
        .where(
            SeasonDay.season_id.in_(season_ids),
            SeasonDay.calendar_date == today,
            SeasonDay.status.in_(["done", "minimal", "rescued"]),
        )
        .distinct()
    ).all()
    return len(done_today)


# ---------------------------------------------------------------------------
# NEWLIFE_2_0.md §3.1 «Главная»: дерево сфер + живая паутинка + привычки +
# продуктивность недели. Геометрия (углы/координаты) считается здесь на
# сервере, а не в шаблоне (Jinja не умеет sin/cos) — простая тригонометрия,
# не бизнес-логика планировщика, поэтому живёт прямо в роутере экрана.
# ---------------------------------------------------------------------------


def _circle_point(cx: float, cy: float, radius: float, index: int, total: int, start_deg: float = -90.0) -> tuple[float, float]:
    """Точка на окружности радиуса `radius` вокруг (cx, cy): `index`-я из
    `total`, равномерно по кругу, первая сверху (-90°), дальше по часовой."""
    if total <= 0:
        return cx, cy
    angle = math.radians(start_deg + (360.0 / total) * index)
    return cx + radius * math.cos(angle), cy + radius * math.sin(angle)


def _sphere_of_season(season: Season) -> Optional[str]:
    # Season не хранит sphere_id (есть только у Goal/SphereState) — сфера
    # сезона определяется через каталог целей, см. app/services/progress.py.
    entry = goal_meta(season.template_id)
    return entry.sphere if entry else None


def _sphere_active_today(db: Session, uid: int, sphere_id: str, today: date) -> bool:
    """Была ли сегодня хоть одна отметка (привычка или день сезона) по этой
    сфере — для яркости линии/иконки на дереве сфер (§3.1 п.1)."""
    habits = db.exec(select(Habit).where(Habit.uid == uid, Habit.active.is_(True))).all()
    sphere_habit_ids = [h.id for h in habits if sphere_id in json.loads(h.spheres_json)]
    if sphere_habit_ids:
        log = db.exec(
            select(HabitLog).where(
                HabitLog.habit_id.in_(sphere_habit_ids),
                HabitLog.log_date == today,
                HabitLog.status.in_(["done", "minimal"]),
            )
        ).first()
        if log:
            return True

    seasons = db.exec(select(Season).where(Season.uid == uid, Season.status == "active")).all()
    sphere_season_ids = [s.id for s in seasons if _sphere_of_season(s) == sphere_id]
    if sphere_season_ids:
        day = db.exec(
            select(SeasonDay).where(
                SeasonDay.season_id.in_(sphere_season_ids),
                SeasonDay.calendar_date == today,
                SeasonDay.status.in_(["done", "minimal", "rescued"]),
            )
        ).first()
        if day:
            return True
    return False


def _build_sphere_tree(db: Session, user: User, today: date, radar_values: list[dict]) -> dict:
    """§3.1 п.1: аватар в центре («Ты · уровень N»), вокруг — иконки только
    выбранных (активных) сфер, линия ярче у сфер с активностью сегодня."""
    states = db.exec(select(SphereState).where(SphereState.uid == user.id, SphereState.active.is_(True))).all()
    active_ids = {s.sphere_id for s in states}
    tree_spheres = [s for s in SPHERES if s.id in active_ids]

    size, center, radius = 280.0, 140.0, 104.0
    nodes = []
    for i, sphere in enumerate(tree_spheres):
        x, y = _circle_point(center, center, radius, i, len(tree_spheres))
        nodes.append(
            {
                "sphere": sphere,
                "x": round(x, 1),
                "y": round(y, 1),
                "active_today": _sphere_active_today(db, user.id, sphere.id, today),
            }
        )

    active_scores = [r["current"] for r in radar_values if r["active"]]
    avg_level = round(sum(active_scores) / len(active_scores)) if active_scores else 0
    return {"size": size, "center": center, "nodes": nodes, "avg_level": avg_level}


def _build_radar_chart(radar_values: list[dict]) -> dict:
    """§3.1 п.2: живая паутинка — сплошной полигон (реальное выполнение за
    14 дней, `sphere_radar_values`), пунктир — точка А, 3-11 осей по
    выбранным сферам пользователя."""
    values = [r for r in radar_values if r["active"]]
    size, center, radius = 260.0, 130.0, 96.0
    n = len(values)

    axes = []
    current_points = []
    baseline_points = []
    for i, entry in enumerate(values):
        lx, ly = _circle_point(center, center, radius + 22, i, n)
        sphere = SPHERE_BY_ID[entry["sphere_id"]]
        axes.append({"sphere": sphere, "lx": round(lx, 1), "ly": round(ly, 1)})

        cur_r = radius * max(0, min(10, entry["current"])) / 10
        base_r = radius * max(0, min(10, entry["baseline"])) / 10
        cx, cy = _circle_point(center, center, cur_r, i, n)
        bx, by = _circle_point(center, center, base_r, i, n)
        current_points.append(f"{cx:.1f},{cy:.1f}")
        baseline_points.append(f"{bx:.1f},{by:.1f}")

    return {
        "size": size,
        "center": center,
        "rings": [round(radius * f) for f in (0.33, 0.66, 1.0)],
        "axes": axes,
        "current_points": " ".join(current_points),
        "baseline_points": " ".join(baseline_points),
        "has_data": n >= 1,
    }


def _home_good_habits(db: Session, uid: int, today: date, limit: int = 4) -> list[dict]:
    """§3.1 п.3: 2-4 самые релевантные (due today) полезные привычки, со
    стриком и отметкой, можно ли ещё нажать «Сделал» сегодня."""
    habits = db.exec(select(Habit).where(Habit.uid == uid, Habit.active.is_(True))).all()
    due = [h for h in habits if today.isoweekday() in json.loads(h.days_json)]
    due.sort(key=lambda h: h.id)

    rows = []
    for h in due[:limit]:
        logs = habit_logs_by_date(db, h.id)
        rows.append(
            {
                "habit": h,
                "today_status": logs.get(today),
                "streak": habit_streak(db, h, today),
            }
        )
    return rows


def _home_bad_habits(db: Session, uid: int, now: datetime, limit: int = 3) -> list[dict]:
    """§3.1 п.4: вредные привычки с таймером воздержания и кнопкой «Сорвался»."""
    bad_habits = db.exec(select(BadHabit).where(BadHabit.uid == uid, BadHabit.active.is_(True))).all()
    rows = []
    for bh in bad_habits[:limit]:
        clean = clean_duration(db, bh, now)
        rows.append({"bad_habit": bh, "clean_days": clean.days, "clean_hours": clean.seconds // 3600})
    return rows


def _build_week_bars(db: Session, user: User, today: date) -> list[dict]:
    """§3.1 п.5: столбцы Пн-Вс, высота = % выполнения, цвет от красного
    через жёлтый к зелёному (посчитан в шаблоне через color-mix на основе
    percent, тут только сами значения + метка дня недели)."""
    monday = week_dates(today)[0]
    bars = week_productivity(db, user.id, monday)
    for i, bar in enumerate(bars):
        bar["label"] = WEEKDAY_LABELS[i]
    return bars


@router.get("/today")
def today_page(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    profile = db.exec(select(Profile).where(Profile.uid == user.id)).first()
    if not has_completed_profile(profile):
        return RedirectResponse("/onboarding", status_code=303)

    today = today_for(user)
    season = _prepare_season(request, user, db)

    season_ctx: dict = {"has_season": False}
    mascot_event = "pending"

    if season:
        if season.status == "finished":
            return RedirectResponse(f"/season/{season.id}/reveal", status_code=303)

        day_number = today_day_number(season, today)
        day = get_day(db, season.id, day_number)
        if day:
            forecast = compute_forecast(db, season, day_number)
            checkins = _wave_today_checkins(db, season, today)
            wave_size = len(db.exec(select(Season.id).where(Season.wave_id == season.wave_id)).all())
            percent = day_number / season.length_days
            mascot_event = {
                "done": "done",
                "minimal": "minimal",
                "rescued": "second_chance_used",
                "missed": "skip",
            }.get(day.status, "wave_start" if day_number == 1 else "pending")
            other_seasons = [s for s in get_active_seasons(db, user.id) if s.id != season.id]
            metric = goal_metric_for_season(season)
            season_ctx = {
                "has_season": True,
                "season": season,
                "day": day,
                "day_number": day_number,
                "metric_kind": metric.kind if metric else "measure",
                "ring_circumference": round(RING_CIRCUMFERENCE, 1),
                "ring_offset": round(RING_CIRCUMFERENCE * (1 - percent), 1),
                "forecast": round(forecast, 1),
                "checkins": checkins,
                "wave_size": wave_size,
                "other_seasons": other_seasons,
                "first_guide_step": first_guide_step(season.template_id, user.language),
                "has_workout_program": season.template_id in WORKOUT_PROGRAM_GOALS,
            }

    checkin = get_checkin(db, user.id, today)
    in_recovery = is_in_recovery_mode(db, user.id, today)
    offer_recovery = False if in_recovery else should_offer_recovery_mode(db, user.id, today)
    schedule_blocks = get_or_build_schedule_for_day(db, user, today)

    show_sleep_hygiene = False
    if profile and profile.sleep_time:
        now_minutes = now_for(user).hour * 60 + now_for(user).minute
        show_sleep_hygiene = methods_catalog.should_show_sleep_hygiene_reminder(now_minutes, parse_hhmm(profile.sleep_time))

    # NEWLIFE_2_0.md Этап 1 п.5: единственный опрос на "Сегодня" — вопрос
    # дня. Недельная рефлексия (app/services/weekly_reflection.py) была
    # вторым опросом на этом же экране — убрана отсюда (см.
    # tests/test_weekly_reflection.py).
    day_question = todays_question(db, user.id, profile, today)

    # NEWLIFE_2_0.md §3.1: дерево сфер, живая паутинка, привычки/вредные
    # привычки со стриком и таймером, продуктивность недели — новая Главная.
    radar_values = sphere_radar_values(db, user.id, today)
    sphere_tree = _build_sphere_tree(db, user, today, radar_values)
    radar_chart = _build_radar_chart(radar_values)
    home_good_habits = _home_good_habits(db, user.id, today)
    home_bad_habits = _home_bad_habits(db, user.id, datetime.now(timezone.utc))
    week_bars = _build_week_bars(db, user, today)

    return render(
        request,
        "today.html",
        {
            **season_ctx,
            "today_date": today,
            "checkin": checkin,
            "in_recovery": in_recovery,
            "offer_recovery": offer_recovery,
            "schedule_blocks": schedule_blocks,
            "show_sleep_hygiene": show_sleep_hygiene,
            "day_question": day_question,
            "minimal_only": bool(profile and profile.has_medical_diagnosis),
            "mascot_phrase": mascot.phrase_for(mascot_event, user.language),
            "mascot_state": mascot.state_for(mascot_event),
            "show_tour": request.query_params.get("tour") == "1",
            "sphere_tree": sphere_tree,
            "radar_chart": radar_chart,
            "home_good_habits": home_good_habits,
            "home_bad_habits": home_bad_habits,
            "week_bars": week_bars,
            "lang": user.language,
        },
    )


@router.post("/today/checkin")
def submit_checkin(
    request: Request,
    energy: int = Form(...),
    stress: int = Form(...),
    mood: int = Form(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    today = today_for(user)
    energy = max(1, min(5, energy))
    stress = max(1, min(5, stress))
    mood = max(1, min(5, mood))
    log_checkin(db, user.id, today, energy, stress, mood)
    return RedirectResponse("/today", status_code=303)


@router.post("/today/question")
def submit_day_question(
    request: Request,
    question_id: str = Form(...),
    option_index: int = Form(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    record_answer(db, user.id, question_id, option_index, today_for(user))
    push_flash(request, "today.question_answered_flash", "success")
    return RedirectResponse("/today", status_code=303)


@router.post("/today/recovery/start")
def recovery_start(
    request: Request,
    obstacle: str = Form(""),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    start_recovery_mode(db, user.id, obstacle or None)
    push_flash(request, "today.recovery_started_flash", "info")
    return RedirectResponse("/today", status_code=303)


@router.post("/today/recovery/decline")
def recovery_decline(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    from app.services.checkin_service import log_method_shown

    log_method_shown(db, user.id, "recovery_mode", "declined", accepted=False)
    return RedirectResponse("/today", status_code=303)


@router.post("/today/switch-season")
def switch_season(
    request: Request,
    season_id: int = Form(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    season = db.get(Season, season_id)
    if season and season.uid == user.id and season.status == "active":
        set_current_season(request, season.id)
    return RedirectResponse("/today", status_code=303)


@router.post("/today/done")
async def mark_done(
    request: Request,
    photo: Optional[UploadFile] = File(None),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    season = _prepare_season(request, user, db)
    if not season:
        return RedirectResponse("/today", status_code=303)
    today = today_for(user)
    day = get_day(db, season.id, today_day_number(season, today))
    if day and day.kind == "measure":
        # Дни-замеры (включая день 1 — точку старта) отмечаются через
        # /measure, не через эту форму (её вообще нет на экране для них).
        return RedirectResponse("/measure", status_code=303)
    if not day or day.status not in ("planned",):
        return RedirectResponse("/today", status_code=303)

    proof_id = None
    if photo is not None and photo.filename:
        data = await photo.read()
        if data:
            filename = save_photo_bytes(data, photo.filename)
            analysis = analyze_photo(f"uploads/{filename}")
            proof = Proof(
                uid=user.id,
                filename=filename,
                content_type=photo.content_type or "image/jpeg",
                phash=analysis["phash"],
                is_blurry=analysis["is_blurry"],
                is_blank=analysis["is_blank"],
            )
            db.add(proof)
            db.commit()
            db.refresh(proof)
            proof_id = proof.id
            if analysis["is_blurry"] or analysis["is_blank"]:
                user.trust_score = apply_trust_penalty(user.trust_score, PENALTY_BLURRY_OR_BLANK_PHOTO)
                db.add(user)
                db.commit()

    day.status = "done"
    day.done_at = engine_now()
    day.proof_id = proof_id
    db.add(day)
    db.commit()
    log_event_safe(db, "day_done", uid=user.id, season_id=season.id)

    push_flash(request, mascot.phrase_for("done", user.language), "success")
    return RedirectResponse("/today", status_code=303)


@router.post("/today/minimal")
def mark_minimal(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    season = _prepare_season(request, user, db)
    if not season:
        return RedirectResponse("/today", status_code=303)
    today = today_for(user)
    day = get_day(db, season.id, today_day_number(season, today))
    if day and day.kind == "measure":
        return RedirectResponse("/measure", status_code=303)
    if day and day.status == "planned":
        day.status = "minimal"
        day.done_at = engine_now()
        db.add(day)
        db.commit()
        log_event_safe(db, "day_minimal", uid=user.id, season_id=season.id)
        push_flash(request, mascot.phrase_for("minimal", user.language), "info")
    return RedirectResponse("/today", status_code=303)


@router.post("/today/rescue")
def rescue_today(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    """Второй шанс — спасти вчерашний (или сегодняшний, если уже отмечен
    missed) пропущенный день, пока окно ещё открыто (§6)."""
    season = _prepare_season(request, user, db)
    if not season:
        return RedirectResponse("/today", status_code=303)
    today = today_for(user)

    missed_days = db.exec(
        select(SeasonDay).where(SeasonDay.season_id == season.id, SeasonDay.status == "missed")
    ).all()
    rescuable = [d for d in missed_days if engine.can_rescue_day(d.calendar_date, today)]

    if not rescuable or season.second_chances_left <= 0:
        push_flash(request, mascot.phrase_for("chances_exhausted", user.language), "info")
        return RedirectResponse("/today", status_code=303)

    day = sorted(rescuable, key=lambda d: d.day_number)[0]
    day.status = "rescued"
    day.done_at = engine_now()
    season.second_chances_left -= 1
    db.add(day)
    db.add(season)
    db.commit()
    log_event_safe(db, "second_chance_used", uid=user.id, season_id=season.id)

    push_flash(request, mascot.phrase_for("second_chance_used", user.language), "success")
    return RedirectResponse("/today", status_code=303)


def engine_now():
    return datetime.now(timezone.utc)
