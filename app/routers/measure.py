"""
«Замер» (§7.4): ввод значения (+ опционально фото), результат относительно
графика, предложение адаптации фазы (решение — за пользователем, §6).
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.auth import require_user
from app.database import get_session
from app.models import Measurement, Proof, SeasonDay, User
from app.rendering import render
from app.seasons import engine
from app.seasons_library.loader import get_template
from app.services import mascot
from app.services.events import log_event_safe
from app.services.seasons import ensure_days_built_for_today, get_current_season, today_day_number
from app.services.trust import PENALTY_BLURRY_OR_BLANK_PHOTO, apply_trust_penalty, is_measurement_plausible
from app.services.uploads import analyze_photo, save_photo_bytes
from app.services.usertime import today_for

router = APIRouter()


@router.get("/measure")
def measure_form(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    season = get_current_season(db, user.id, request)
    if not season:
        return RedirectResponse("/onboarding", status_code=303)
    template = get_template(season.template_id)
    return render(
        request,
        "measure.html",
        {"season": season, "template": template, "result": None, "lang": user.language},
    )


@router.post("/measure")
async def measure_submit(
    request: Request,
    value: float = Form(...),
    secondary_value: Optional[float] = Form(None),
    photo: Optional[UploadFile] = File(None),
    photo_pose: Optional[str] = Form(None),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    season = get_current_season(db, user.id, request)
    if not season:
        return RedirectResponse("/onboarding", status_code=303)

    today = today_for(user)
    ensure_days_built_for_today(db, season, today)
    template = get_template(season.template_id)

    previous = db.exec(
        select(Measurement.value)
        .where(Measurement.season_id == season.id)
        .order_by(Measurement.day_number.desc())
    ).first()

    plausible = is_measurement_plausible(previous, value)
    if not plausible:
        user.trust_score = apply_trust_penalty(user.trust_score, 20)
        db.add(user)

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

    day_number = today_day_number(season, today)
    measurement = Measurement(
        season_id=season.id,
        day_number=day_number,
        value=value,
        secondary_value=secondary_value,
        measured_at=datetime.now(timezone.utc),
        proof_id=proof_id,
        photo_pose=photo_pose,
    )
    db.add(measurement)

    day = db.exec(
        select(SeasonDay).where(SeasonDay.season_id == season.id, SeasonDay.day_number == day_number)
    ).first()
    if day and day.status == "planned":
        day.status = "done"
        day.done_at = datetime.now(timezone.utc)
        day.proof_id = proof_id
        db.add(day)

    db.commit()
    log_event_safe(db, "measurement_logged", uid=user.id, season_id=season.id)

    phase = next(p for p in template.phases if p.phase == season.current_phase)
    expected_value = season.baseline_value + phase.days[0].expected_progress * day_number
    suggested_phase = engine.adapt_phase(
        template, season.current_phase, value, expected_value, template.safety.max_phase_jump
    )

    better = value > expected_value if template.metric.direction == "up" else value < expected_value
    mascot_event = "measure_better" if better else "measure_worse"

    return render(
        request,
        "measure.html",
        {
            "season": season,
            "template": template,
            "result": {
                "value": value,
                "expected": round(expected_value, 1),
                "plausible": plausible,
                "suggested_phase": suggested_phase,
                "current_phase": season.current_phase,
            },
            "mascot_phrase": mascot.phrase_for(mascot_event, user.language),
            "mascot_state": mascot.state_for(mascot_event),
            "lang": user.language,
        },
    )


@router.post("/measure/adapt")
def measure_adapt(
    request: Request,
    accept: bool = Form(...),
    phase: int = Form(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    season = get_current_season(db, user.id, request)
    if season and accept:
        season.current_phase = phase
        db.add(season)
        db.commit()
    if season:
        return RedirectResponse(f"/season/{season.id}", status_code=303)
    return RedirectResponse("/seasons", status_code=303)
