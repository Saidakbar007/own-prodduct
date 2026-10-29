"""
«Сезон» (§7.3): календарь дней (все статусы), график замеров, текущая фаза.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.auth import require_user
from app.database import get_session
from app.models import Measurement, SeasonDay, User
from app.rendering import render
from app.services.seasons import ensure_days_built_for_today, get_active_season, sync_season_state
from app.services.usertime import today_for

router = APIRouter()


@router.get("/season")
def season_page(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    season = get_active_season(db, user.id)
    if not season:
        return RedirectResponse("/onboarding", status_code=303)

    today = today_for(user)
    ensure_days_built_for_today(db, season, today)
    season = sync_season_state(db, season, today)

    days = db.exec(
        select(SeasonDay).where(SeasonDay.season_id == season.id).order_by(SeasonDay.day_number)
    ).all()
    measurements = db.exec(
        select(Measurement).where(Measurement.season_id == season.id).order_by(Measurement.day_number)
    ).all()

    today_number = (today - season.start_date).days + 1
    sparkline = _build_sparkline(measurements)

    return render(
        request,
        "season.html",
        {
            "season": season,
            "days": days,
            "measurements": measurements,
            "today_number": today_number,
            "sparkline": sparkline,
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
