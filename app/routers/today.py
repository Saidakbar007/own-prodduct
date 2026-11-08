"""
«Сегодня» (§14 NEWLIFE_v8 / §7.2 Сезонов): чек-ин энергии/стресса/настроения,
главное действие дня (сезон, если есть), лента дня по времени (расписание),
ведущий. Единственный экран, который реально нужен каждый день. Сезон теперь
необязателен — "Сегодня" работает и для человека без активной цели (только
привычки/расписание), обязателен лишь заполненный профиль (точка А).
"""

import math
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.auth import require_user
from app.database import get_session
from app.models import Profile, Proof, Season, SeasonDay, User
from app.newlife import methods as methods_catalog
from app.newlife.goal_catalog import first_guide_step
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
from app.services.newlife_onboarding import has_completed_profile
from app.newlife.scheduler import parse_hhmm
from app.services.schedule_service import get_or_build_schedule_for_day
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
