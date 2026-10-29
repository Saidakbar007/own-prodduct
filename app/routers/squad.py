"""
«Состав» (§7.6) — облегчённая версия Фазы 2: до 8 человек волны с похожей
целью, ник, "день N", отметился ли сегодня, серия дней подряд. Реакции и
полноценная анонимность/выход из состава — Фаза 3.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.auth import require_user
from app.database import get_session
from app.models import Season, SeasonDay, User
from app.rendering import render
from app.services.seasons import get_active_season, today_day_number
from app.services.trust import meets_squad_trust_threshold
from app.services.usertime import today_for

router = APIRouter()

MAX_SQUAD_SIZE = 8


def _streak(db: Session, season_id: int, up_to_day: int) -> int:
    rows = db.exec(
        select(SeasonDay.status)
        .where(SeasonDay.season_id == season_id, SeasonDay.day_number <= up_to_day)
        .order_by(SeasonDay.day_number.desc())
    ).all()
    streak = 0
    for status in rows:
        if status in ("done", "minimal", "rescued"):
            streak += 1
        elif status == "rest":
            continue
        else:
            break
    return streak


@router.get("/squad")
def squad_page(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    season = get_active_season(db, user.id)
    if not season:
        return RedirectResponse("/onboarding", status_code=303)

    today = today_for(user)
    rows_query = db.exec(
        select(Season, User).where(Season.wave_id == season.wave_id).join(User, Season.uid == User.id)
    ).all()

    members = []
    for member_season, member_user in rows_query:
        if not meets_squad_trust_threshold(member_user.trust_score):
            continue
        day_number = today_day_number(member_season, today)
        today_status = db.exec(
            select(SeasonDay.status).where(
                SeasonDay.season_id == member_season.id, SeasonDay.day_number == day_number
            )
        ).first()
        members.append(
            {
                "is_me": member_user.id == user.id,
                "nick": member_user.name.split(" ")[0] if member_user.id == user.id else member_user.login,
                "day_number": max(day_number, 0),
                "checked_in_today": today_status in ("done", "minimal", "rescued"),
                "streak": _streak(db, member_season.id, day_number),
            }
        )

    members.sort(key=lambda m: (-m["streak"], m["nick"]))
    overflow = max(0, len(members) - MAX_SQUAD_SIZE)

    return render(
        request,
        "squad.html",
        {"members": members[:MAX_SQUAD_SIZE], "overflow": overflow, "lang": user.language},
    )
