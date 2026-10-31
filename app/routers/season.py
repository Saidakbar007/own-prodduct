"""
«Сезоны»: хаб (текущие сезоны, каталог шаблонов, полка завершённых) и
детальная страница одного сезона — «откуда → куда», день N из M, прогноз
простыми словами, компактный календарь, «Проверка результата» (бывший
«Замер», §7.3/§7.4 ТЗ, переименовано UX-правкой).
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.auth import require_user
from app.database import get_session
from app.models import Measurement, Reveal, Season, SeasonDay, User
from app.rendering import render
from app.seasons_library.catalog_meta import meta_for, poster_hero_for
from app.seasons_library.loader import load_library
from app.services.seasons import (
    MAX_ACTIVE_SEASONS,
    compute_forecast,
    ensure_days_built_for_today,
    get_active_seasons,
    get_current_season,
    sync_season_state,
)
from app.services.usertime import today_for

router = APIRouter()


@router.get("/seasons")
def seasons_hub(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    today = today_for(user)
    active = get_active_seasons(db, user.id)
    for season in active:
        ensure_days_built_for_today(db, season, today)
        sync_season_state(db, season, today)
    # sync_season_state может перевести сезон в "finished" — перечитываем список.
    active = get_active_seasons(db, user.id)

    active_cards = [
        {
            "season": s,
            "poster_hero": poster_hero_for(s.template_id),
            "day_number": max(1, (today - s.start_date).days + 1),
        }
        for s in active
    ]

    completed = db.exec(
        select(Season)
        .where(Season.uid == user.id, Season.status == "finished")
        .order_by(Season.created_at.desc())
    ).all()
    reveals = {s.id: db.exec(select(Reveal).where(Reveal.season_id == s.id)).first() for s in completed}

    catalog = [
        {
            "template": t,
            "meta": meta_for(t.id),
            "poster_hero": poster_hero_for(t.id),
        }
        for t in sorted(load_library().values(), key=lambda t: t.id)
    ]

    return render(
        request,
        "seasons_hub.html",
        {
            "active_cards": active_cards,
            "completed": completed,
            "reveals": reveals,
            "catalog": catalog,
            "can_start": len(active) < MAX_ACTIVE_SEASONS,
            "lang": user.language,
        },
    )


@router.get("/season")
def season_redirect(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    """Удобная ссылка без id — на текущий выбранный сезон."""
    season = get_current_season(db, user.id, request)
    if season:
        return RedirectResponse(f"/season/{season.id}", status_code=303)
    return RedirectResponse("/seasons", status_code=303)


def _own_season(db: Session, season_id: int, user: User) -> Season:
    season = db.get(Season, season_id)
    if not season or season.uid != user.id:
        raise HTTPException(status_code=404)
    return season


@router.get("/season/{season_id}")
def season_detail(
    season_id: int, request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)
):
    season = _own_season(db, season_id, user)

    today = today_for(user)
    if season.status == "active":
        ensure_days_built_for_today(db, season, today)
        season = sync_season_state(db, season, today)

    if season.status == "finished":
        return RedirectResponse(f"/season/{season.id}/reveal", status_code=303)

    days = db.exec(
        select(SeasonDay).where(SeasonDay.season_id == season.id).order_by(SeasonDay.day_number)
    ).all()
    measurements = db.exec(
        select(Measurement).where(Measurement.season_id == season.id).order_by(Measurement.day_number)
    ).all()

    today_number = max(1, (today - season.start_date).days + 1)
    sparkline = _build_sparkline(measurements)
    forecast = compute_forecast(db, season, today_number)

    present_statuses = sorted({d.status for d in days if d.status != "planned"})
    if any(d.status == "planned" and d.calendar_date >= today for d in days):
        present_statuses.append("future")

    return render(
        request,
        "season_detail.html",
        {
            "season": season,
            "days": days,
            "measurements": measurements,
            "today_number": today_number,
            "sparkline": sparkline,
            "forecast": round(forecast, 1),
            "present_statuses": present_statuses,
            "poster_hero": poster_hero_for(season.template_id),
            "lang": user.language,
        },
    )


def _build_sparkline(measurements, width: int = 280, height: int = 48) -> dict:
    """Готовые точки для SVG-полилинии замеров (без JS, считаем на сервере)."""
    values = [m.value for m in measurements]
    if len(values) < 2:
        return {"line": "", "area": "", "has_data": False}

    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    step = width / (len(values) - 1)

    points = [
        (round(i * step, 1), round(height - ((v - lo) / span) * height, 1))
        for i, v in enumerate(values)
    ]
    line = " ".join(f"{x} {y}" for x, y in points)
    area = f"0 {height} " + line + f" {width} {height}"
    return {
        "line": "M" + " L".join(f"{x} {y}" for x, y in points),
        "area": "M" + f"0 {height} L" + " L".join(f"{x} {y}" for x, y in points) + f" L{width} {height} Z",
        "last_x": points[-1][0],
        "last_y": points[-1][1],
        "has_data": True,
    }
