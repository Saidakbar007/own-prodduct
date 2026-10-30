"""
Админка (§14 ТЗ): дашборд метрик, галерея шаблонов ("Сезоны"), песочница.
404 (не 403) для всех, кто не в ADMIN_LOGINS — см. app.auth.require_admin.
"""

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.auth import require_admin
from app.database import get_session
from app.models import CustomTemplateDraft, Measurement, Season, SeasonDay, User
from app.rendering import render
from app.seasons.schema import SeasonTemplate
from app.seasons_library.loader import get_template, load_approved_custom_templates, load_library
from app.services.admin_stats import (
    funnel_counts,
    next_season_rate,
    retention_overview,
    reveal_completion_rate,
    virality,
)
from app.services.episodes import get_or_create_episode
from app.services.reveals import get_or_create_reveal
from app.services.seasons import build_all_days, create_season, sync_season_state

router = APIRouter(prefix="/admin")


@router.get("")
def dashboard(request: Request, user: User = Depends(require_admin), db: Session = Depends(get_session)):
    cohort_day = date.today() - timedelta(days=30)
    return render(
        request,
        "admin/dashboard.html",
        {
            "funnel": funnel_counts(db),
            "retention": retention_overview(db, cohort_day),
            "reveal_rate": reveal_completion_rate(db),
            "next_season_rate": next_season_rate(db),
            "virality": virality(db),
            "lang": user.language,
        },
    )


@router.get("/gallery")
def gallery(request: Request, user: User = Depends(require_admin), db: Session = Depends(get_session)):
    load_approved_custom_templates(db)
    library_templates = list(load_library().values())
    drafts = db.exec(select(CustomTemplateDraft).order_by(CustomTemplateDraft.created_at.desc())).all()
    return render(
        request,
        "admin/gallery.html",
        {"templates": library_templates, "drafts": drafts, "lang": user.language},
    )


@router.post("/gallery/approve/{draft_id}")
def approve_draft(draft_id: int, user: User = Depends(require_admin), db: Session = Depends(get_session)):
    draft = db.get(CustomTemplateDraft, draft_id)
    if draft:
        draft.approved = True
        db.add(draft)
        db.commit()
    return RedirectResponse("/admin/gallery", status_code=303)


@router.get("/sandbox")
def sandbox_home(request: Request, user: User = Depends(require_admin), db: Session = Depends(get_session)):
    load_approved_custom_templates(db)
    seasons = db.exec(select(Season).where(Season.uid == user.id).order_by(Season.created_at.desc())).all()
    tiles = sorted(load_library().values(), key=lambda t: t.id)
    return render(
        request,
        "admin/sandbox.html",
        {"templates": tiles, "seasons": seasons, "season_detail": None, "lang": user.language},
    )


@router.post("/sandbox/create")
def sandbox_create(
    request: Request,
    template_id: str = Form(...),
    length_days: int = Form(...),
    baseline_value: float = Form(...),
    days_ago: int = Form(0),
    user: User = Depends(require_admin),
    db: Session = Depends(get_session),
):
    template = get_template(template_id)
    reference_date = date.today() - timedelta(days=max(0, days_ago) + 14)
    season = create_season(
        db,
        uid=user.id,
        template_id=template.id,
        length_days=length_days,
        baseline_value=baseline_value,
        reference_date=reference_date,
    )
    build_all_days(db, season)
    return RedirectResponse(f"/admin/sandbox/{season.id}", status_code=303)


def _own_sandbox_season(db: Session, season_id: int, user: User) -> Season:
    season = db.get(Season, season_id)
    if not season or season.uid != user.id:
        raise HTTPException(status_code=404)
    return season


@router.get("/sandbox/{season_id}")
def sandbox_detail(
    season_id: int, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_session)
):
    season = _own_sandbox_season(db, season_id, user)
    days = db.exec(
        select(SeasonDay).where(SeasonDay.season_id == season.id).order_by(SeasonDay.day_number)
    ).all()
    measurements = db.exec(
        select(Measurement).where(Measurement.season_id == season.id).order_by(Measurement.day_number)
    ).all()
    seasons = db.exec(select(Season).where(Season.uid == user.id).order_by(Season.created_at.desc())).all()
    tiles = sorted(load_library().values(), key=lambda t: t.id)
    return render(
        request,
        "admin/sandbox.html",
        {
            "templates": tiles,
            "seasons": seasons,
            "season_detail": season,
            "days": days,
            "measurements": measurements,
            "lang": user.language,
        },
    )


@router.post("/sandbox/{season_id}/mark")
def sandbox_mark(
    season_id: int,
    day_number: int = Form(...),
    status: str = Form(...),
    user: User = Depends(require_admin),
    db: Session = Depends(get_session),
):
    season = _own_sandbox_season(db, season_id, user)
    day = db.exec(
        select(SeasonDay).where(SeasonDay.season_id == season.id, SeasonDay.day_number == day_number)
    ).first()
    if day and status in ("planned", "done", "minimal", "missed", "rescued", "rest"):
        day.status = status
        if status == "rescued":
            season.second_chances_left = max(0, season.second_chances_left - 1)
            db.add(season)
        db.add(day)
        db.commit()
    return RedirectResponse(f"/admin/sandbox/{season_id}", status_code=303)


@router.post("/sandbox/{season_id}/measure")
def sandbox_measure(
    season_id: int,
    day_number: int = Form(...),
    value: float = Form(...),
    user: User = Depends(require_admin),
    db: Session = Depends(get_session),
):
    season = _own_sandbox_season(db, season_id, user)
    db.add(Measurement(season_id=season.id, day_number=day_number, value=value))
    db.commit()
    return RedirectResponse(f"/admin/sandbox/{season_id}", status_code=303)


@router.post("/sandbox/{season_id}/episode")
def sandbox_episode(
    season_id: int,
    week_number: int = Form(...),
    user: User = Depends(require_admin),
    db: Session = Depends(get_session),
):
    season = _own_sandbox_season(db, season_id, user)
    get_or_create_episode(db, season, week_number)
    return RedirectResponse(f"/season/{season_id}/episode/{week_number}", status_code=303)


@router.post("/sandbox/{season_id}/finish")
def sandbox_finish(
    season_id: int, user: User = Depends(require_admin), db: Session = Depends(get_session)
):
    """Принудительно завершает сезон и генерирует Reveal — чтобы увидеть
    финал без реального прохождения всех дней."""
    season = _own_sandbox_season(db, season_id, user)
    season.status = "finished"
    db.add(season)
    db.commit()
    get_or_create_reveal(db, season)
    return RedirectResponse(f"/season/{season_id}/reveal", status_code=303)
