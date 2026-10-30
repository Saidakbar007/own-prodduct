"""
«Состав» (§7.6, Фаза 3): до 8 человек волны с похожей целью — ник
(анонимно по умолчанию), "день N", отметился ли сегодня, серия дней,
реакции-"огоньки". Выйти — в один клик.
"""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.auth import require_user
from app.database import get_session
from app.models import Season, SeasonDay, User
from app.rendering import render
from app.services.events import log_event_safe
from app.services.seasons import get_active_season, today_day_number
from app.services.squads import (
    active_members,
    add_reaction,
    display_name,
    leave_squad,
    my_squad_membership,
    reaction_count,
    set_anonymous,
)
from app.services.usertime import today_for

router = APIRouter()


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

    membership = my_squad_membership(db, user.id, season.id)
    if not membership:
        return render(request, "squad.html", {"members": [], "overflow": 0, "membership": None, "lang": user.language})

    today = today_for(user)
    members_rows = []
    for member in active_members(db, membership.squad_id):
        member_user = db.get(User, member.uid)
        member_season = db.get(Season, member.season_id)
        day_number = today_day_number(member_season, today)
        today_status = db.exec(
            select(SeasonDay.status).where(
                SeasonDay.season_id == member_season.id, SeasonDay.day_number == day_number
            )
        ).first()
        members_rows.append(
            {
                "uid": member_user.id,
                "is_me": member_user.id == user.id,
                "nick": display_name(member_user, member),
                "day_number": max(day_number, 0),
                "checked_in_today": today_status in ("done", "minimal", "rescued"),
                "streak": _streak(db, member_season.id, max(day_number, 0)),
                "reactions_today": reaction_count(db, membership.squad_id, member_user.id, today),
                "i_reacted_today": False,
            }
        )

    members_rows.sort(key=lambda m: (-m["streak"], m["nick"]))

    return render(
        request,
        "squad.html",
        {
            "members": members_rows,
            "overflow": 0,
            "membership": membership,
            "lang": user.language,
        },
    )


@router.post("/squad/react")
def react(
    request: Request,
    to_uid: int = Form(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    season = get_active_season(db, user.id)
    membership = my_squad_membership(db, user.id, season.id) if season else None
    if membership and add_reaction(db, membership.squad_id, user.id, to_uid, today_for(user)):
        log_event_safe(db, "squad_reaction", uid=user.id, season_id=season.id)
    return RedirectResponse("/squad", status_code=303)


@router.post("/squad/leave")
def leave(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    season = get_active_season(db, user.id)
    membership = my_squad_membership(db, user.id, season.id) if season else None
    if membership:
        leave_squad(db, user.id, membership.squad_id)
    return RedirectResponse("/squad", status_code=303)


@router.post("/squad/anonymous")
def toggle_anonymous(
    request: Request,
    anonymous: bool = Form(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    season = get_active_season(db, user.id)
    membership = my_squad_membership(db, user.id, season.id) if season else None
    if membership:
        set_anonymous(db, user.id, membership.squad_id, anonymous)
    return RedirectResponse("/squad", status_code=303)
