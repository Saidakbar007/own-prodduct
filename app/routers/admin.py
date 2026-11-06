"""
Админка (§14 Сезоны / §15 NewLife v8): дашборд метрик, галерея шаблонов,
каталоги (цели/привычки), сферы, песочницы сезона и расписания.
404 (не 403) для всех, кто не в ADMIN_LOGINS — см. app.auth.require_admin.
"""

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.auth import require_admin
from app.database import get_session
from app.models import CustomTemplateDraft, Measurement, Season, SeasonDay, SphereState, User
from app.newlife.habit_catalog import load_bad_habit_catalog, load_habit_catalog
from app.newlife.question_bank import load_question_bank
from app.newlife.scheduler import format_hhmm
from app.newlife.spheres import SPHERES
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
from app.services.schedule_service import build_schedule_for_day
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


@router.get("/spheres")
def spheres_admin(request: Request, user: User = Depends(require_admin), db: Session = Depends(get_session)):
    """§15 NewLife v8: сколько людей активны в каждой сфере и средний уровень."""
    rows = []
    for sphere in SPHERES:
        states = db.exec(select(SphereState).where(SphereState.sphere_id == sphere.id, SphereState.active.is_(True))).all()
        avg_level = round(sum(s.level for s in states) / len(states), 1) if states else None
        rows.append({"sphere": sphere, "active_count": len(states), "avg_level": avg_level})
    return render(request, "admin/spheres.html", {"rows": rows, "lang": user.language})


@router.get("/catalog")
def catalog_admin(request: Request, user: User = Depends(require_admin)):
    """§15: каталог целей (шаблоны сезонов) + каталог привычек/плохих
    привычек — всё версионируется в YAML/git, здесь только просмотр."""
    goal_templates = sorted(load_library().values(), key=lambda t: t.id)
    habits = load_habit_catalog()
    triggers, bad_habits = load_bad_habit_catalog()
    return render(
        request,
        "admin/catalog.html",
        {"goal_templates": goal_templates, "habits": habits, "bad_habits": bad_habits, "triggers": triggers, "lang": user.language},
    )


@router.get("/questions")
def questions_admin(request: Request, user: User = Depends(require_admin)):
    """PRD 1.0 F7: банк "вопрос дня" — версионируется в YAML/git, здесь
    только просмотр (как /admin/catalog для целей/привычек)."""
    bank = load_question_bank()
    rows = [{"sphere": sphere, "questions": bank.get(sphere.id, [])} for sphere in SPHERES]
    return render(request, "admin/questions.html", {"rows": rows, "lang": user.language})


@router.get("/schedule-sandbox")
def schedule_sandbox(
    request: Request,
    on_date: Optional[date] = None,
    user: User = Depends(require_admin),
    db: Session = Depends(get_session),
):
    """§15: песочница расписания — прогнать планировщик на дату для своего
    же аккаунта, не сохраняя результат, чтобы увидеть алгоритм в деле."""
    target_date = on_date or date.today()
    result = build_schedule_for_day(db, user, target_date)
    blocks = [
        {"start": format_hhmm(b.start_min), "end": format_hhmm(b.end_min), "kind": b.kind, "title": b.title}
        for b in result.blocks
    ]
    return render(
        request,
        "admin/schedule_sandbox.html",
        {"target_date": target_date, "blocks": blocks, "unplaced": result.unplaced, "messages": result.messages, "lang": user.language},
    )
