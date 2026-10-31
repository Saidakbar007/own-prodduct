"""
«Сегодня» (§7.2): день N из сезона, карточка действия дня, прогноз, строка
состава волны. Единственный экран, который реально нужен каждый день.
"""

import math
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.auth import require_user
from app.database import get_session
from app.models import Proof, Season, SeasonDay, User
from app.rendering import render
from app.seasons import engine
from app.services import mascot
from app.services.events import log_event_safe
from app.services.flash import push_flash
from app.services.seasons import (
    compute_forecast,
    ensure_days_built_for_today,
    get_active_seasons,
    get_current_season,
    get_day,
    set_current_season,
    sync_season_state,
    today_day_number,
)
from app.services.trust import PENALTY_BLURRY_OR_BLANK_PHOTO, apply_trust_penalty
from app.services.uploads import analyze_photo, save_photo_bytes
from app.services.usertime import today_for

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
    season = _prepare_season(request, user, db)
    if not season:
        return RedirectResponse("/onboarding", status_code=303)

    if season.status == "finished":
        return RedirectResponse(f"/season/{season.id}/reveal", status_code=303)

    today = today_for(user)
    day_number = today_day_number(season, today)
    day = get_day(db, season.id, day_number)
    if not day:
        # Защитный случай (не должен случаться: день 1 строится сразу при
        # создании сезона) — безопаснее отправить в онбординг, чем падать.
        return RedirectResponse("/onboarding", status_code=303)

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

    return render(
        request,
        "today.html",
        {
            "season": season,
            "day": day,
            "day_number": day_number,
            "ring_circumference": round(RING_CIRCUMFERENCE, 1),
            "ring_offset": round(RING_CIRCUMFERENCE * (1 - percent), 1),
            "forecast": round(forecast, 1),
            "checkins": checkins,
            "wave_size": wave_size,
            "mascot_phrase": mascot.phrase_for(mascot_event, user.language),
            "mascot_state": mascot.state_for(mascot_event),
            "other_seasons": other_seasons,
            "show_tour": request.query_params.get("tour") == "1",
            "lang": user.language,
        },
    )


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
        return RedirectResponse("/onboarding", status_code=303)
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
        return RedirectResponse("/onboarding", status_code=303)
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
        return RedirectResponse("/onboarding", status_code=303)
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
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)
