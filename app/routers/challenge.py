"""
Вызов «Спорим?» (§7 п.7, Фаза 3).
"""

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.auth import require_user
from app.database import get_session
from app.models import Challenge, ChallengeDispute, Season, SeasonDay, User
from app.rendering import render
from app.services.challenges import (
    accept_challenge,
    confirm_dispute,
    counted_progress,
    create_challenge,
    decline_challenge,
    determine_winner,
    dispute_day,
    get_by_invite_code,
    pending_disputed_days,
)
from app.services.collusion import is_suspicious_pair
from app.services.flash import push_flash
from app.services.seasons import get_active_season, today_day_number
from app.services.usertime import today_for

router = APIRouter()


@router.post("/challenge/create")
def create(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    season = get_active_season(db, user.id)
    if not season:
        return RedirectResponse("/onboarding", status_code=303)
    challenge = create_challenge(db, user.id, season.id)
    return RedirectResponse(f"/challenge/{challenge.id}", status_code=303)


@router.get("/challenge/join/{code}")
def join_page(code: str, request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    challenge = get_by_invite_code(db, code)
    if not challenge:
        raise HTTPException(status_code=404)
    if challenge.from_uid == user.id:
        return RedirectResponse(f"/challenge/{challenge.id}", status_code=303)
    if challenge.status != "pending":
        raise HTTPException(status_code=404)

    from_user = db.get(User, challenge.from_uid)
    from_season = db.get(Season, challenge.season_id_from)
    my_season = get_active_season(db, user.id)
    can_accept = bool(my_season and my_season.template_id == from_season.template_id)

    return render(
        request,
        "challenge_join.html",
        {
            "challenge": challenge,
            "from_user": from_user,
            "from_season": from_season,
            "can_accept": can_accept,
            "lang": user.language,
        },
    )


@router.post("/challenge/join/{code}/accept")
def accept(code: str, request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    challenge = get_by_invite_code(db, code)
    if not challenge or challenge.status != "pending" or challenge.from_uid == user.id:
        raise HTTPException(status_code=404)

    my_season = get_active_season(db, user.id)
    from_season = db.get(Season, challenge.season_id_from)
    if not my_season or my_season.template_id != from_season.template_id:
        push_flash(request, "challenge.need_matching_season", "error")
        return RedirectResponse(f"/challenge/join/{code}", status_code=303)

    accept_challenge(db, challenge, user.id, my_season.id)

    if is_suspicious_pair(db, challenge.from_uid, user.id):
        # Не блокируем вызов — просто небольшой штраф на будущее (§3: анти-сговор).
        for uid in (challenge.from_uid, user.id):
            u = db.get(User, uid)
            u.trust_score = max(0, u.trust_score - 5)
            db.add(u)
        db.commit()

    return RedirectResponse(f"/challenge/{challenge.id}", status_code=303)


@router.post("/challenge/join/{code}/decline")
def decline(code: str, user: User = Depends(require_user), db: Session = Depends(get_session)):
    challenge = get_by_invite_code(db, code)
    if challenge and challenge.from_uid != user.id:
        decline_challenge(db, challenge)
    return RedirectResponse("/today", status_code=303)


def _side(db: Session, season_id: int, uid: int, challenge_id: int, today, label: str) -> dict:
    season = db.get(Season, season_id)
    user = db.get(User, uid)
    day_number = max(today_day_number(season, today), 0)
    counted = counted_progress(db, season_id, challenge_id, uid)
    disputed_today_pending = pending_disputed_days(db, challenge_id, uid)
    return {
        "label": label,
        "uid": uid,
        "name": user.name,
        "day_number": day_number,
        "length_days": season.length_days,
        "counted": counted,
        "pending_disputes": sorted(disputed_today_pending),
    }


@router.get("/challenge/{challenge_id}")
def duel(challenge_id: int, request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    challenge = db.get(Challenge, challenge_id)
    if not challenge or user.id not in (challenge.from_uid, challenge.to_uid):
        raise HTTPException(status_code=404)

    today = today_for(user)
    me_uid = user.id
    opponent_uid = challenge.to_uid if challenge.from_uid == me_uid else challenge.from_uid
    my_season_id = challenge.season_id_from if challenge.from_uid == me_uid else challenge.season_id_to

    sides = None
    if challenge.status == "active":
        opponent_season_id = challenge.season_id_to if challenge.from_uid == me_uid else challenge.season_id_from
        sides = {
            "me": _side(db, my_season_id, me_uid, challenge.id, today, "Я"),
            "opponent": _side(db, opponent_season_id, opponent_uid, challenge.id, today, "Соперник"),
        }

    return render(
        request,
        "challenge_duel.html",
        {
            "challenge": challenge,
            "sides": sides,
            "invite_url": f"/challenge/join/{challenge.invite_code}",
            "lang": user.language,
        },
    )


@router.post("/challenge/{challenge_id}/dispute")
def dispute(
    challenge_id: int,
    day_number: int = Form(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    challenge = db.get(Challenge, challenge_id)
    if not challenge or challenge.status != "active" or user.id not in (challenge.from_uid, challenge.to_uid):
        raise HTTPException(status_code=404)
    opponent_uid = challenge.to_uid if challenge.from_uid == user.id else challenge.from_uid
    dispute_day(db, challenge.id, day_number, uid=opponent_uid, disputed_by=user.id)
    return RedirectResponse(f"/challenge/{challenge_id}", status_code=303)


@router.post("/challenge/{challenge_id}/confirm")
def confirm(
    challenge_id: int,
    day_number: int = Form(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    challenge = db.get(Challenge, challenge_id)
    if not challenge:
        raise HTTPException(status_code=404)
    existing = db.exec(
        select(ChallengeDispute).where(
            ChallengeDispute.challenge_id == challenge_id,
            ChallengeDispute.day_number == day_number,
            ChallengeDispute.uid == user.id,
            ChallengeDispute.status == "pending",
        )
    ).first()
    if existing:
        confirm_dispute(db, existing)
    return RedirectResponse(f"/challenge/{challenge_id}", status_code=303)
