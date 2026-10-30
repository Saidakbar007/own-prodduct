"""
«Профиль» (§7.9): аватар (3D-герой), полка пройденных сезонов, настройки
(тема, язык, часовой пояс, приватность), выход.
"""

import os
from datetime import datetime, timezone as dt_timezone

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.auth import require_user
from app.database import get_session
from app.models import Proof, Reveal, Season, User
from app.rendering import render
from app.services.flash import push_flash
from app.services.usertime import can_change_timezone, is_valid_timezone

router = APIRouter()

HERO_STAGES = 5


def hero_stage_for(completed_count: int) -> int:
    return min(HERO_STAGES, 1 + completed_count)


@router.get("/profile")
def profile_page(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    completed = db.exec(
        select(Season)
        .where(Season.uid == user.id, Season.status == "finished")
        .order_by(Season.created_at.desc())
    ).all()
    reveals = {
        s.id: db.exec(select(Reveal).where(Reveal.season_id == s.id)).first() for s in completed
    }
    stage = hero_stage_for(len(completed))

    return render(
        request,
        "profile.html",
        {
            "user": user,
            "completed": completed,
            "reveals": reveals,
            "hero_stage": stage,
            "can_change_timezone": can_change_timezone(user),
            "lang": user.language,
        },
    )


@router.post("/profile/language")
def set_language(request: Request, language: str = Form(...), user: User = Depends(require_user), db: Session = Depends(get_session)):
    if language in ("ru", "uz"):
        user.language = language
        db.add(user)
        db.commit()
    return RedirectResponse("/profile", status_code=303)


@router.post("/profile/timezone")
def set_timezone(request: Request, timezone: str = Form(...), user: User = Depends(require_user), db: Session = Depends(get_session)):
    if not can_change_timezone(user):
        push_flash(request, "profile.error_timezone_cooldown", "error")
        return RedirectResponse("/profile", status_code=303)
    if is_valid_timezone(timezone):
        user.timezone = timezone
        user.timezone_changed_at = datetime.now(dt_timezone.utc)
        db.add(user)
        db.commit()
    return RedirectResponse("/profile", status_code=303)


@router.post("/profile/delete-photos")
def delete_all_photos(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    """§9: кнопка "удалить все мои фото"."""
    proofs = db.exec(select(Proof).where(Proof.uid == user.id)).all()
    for proof in proofs:
        path = os.path.join("uploads", proof.filename)
        if os.path.exists(path):
            os.remove(path)
        db.delete(proof)
    db.commit()
    push_flash(request, "profile.photos_deleted", "success")
    return RedirectResponse("/profile", status_code=303)
