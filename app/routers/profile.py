"""
Профиль пользователя: вес, рост, семейное положение.
"""

from datetime import datetime, timezone as dt_timezone

from fastapi import APIRouter, Depends, Form, Request
from sqlmodel import Session

from app.auth import require_user
from app.database import get_session
from app.models import User
from app.rendering import render
from app.services.flash import push_flash
from app.services.pentagon import pentagon_chart
from app.services.spheres import all_spheres_progress
from app.services.usertime import TIMEZONE_CHANGE_COOLDOWN_DAYS, can_change_timezone, is_valid_timezone

router = APIRouter()


def _profile_context(db: Session, user: User, saved: bool = False) -> dict:
    return {
        "user": user,
        "saved": saved,
        "hero_chart": pentagon_chart(all_spheres_progress(db, user.id)),
        "can_change_timezone": can_change_timezone(user),
    }


@router.get("/profile")
def profile_page(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    """Показывает текущие данные профиля."""
    return render(request, "profile.html", _profile_context(db, user), db=db, user=user)


@router.post("/profile")
def profile_update(
    request: Request,
    weight: float = Form(None),
    hight: float = Form(None),
    familly_stat: str = Form(None),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """Сохраняет изменения профиля. Пользователь может менять только свои данные."""
    user.weight = weight
    user.hight = hight
    user.familly_stat = familly_stat
    db.add(user)
    db.commit()
    db.refresh(user)
    return render(request, "profile.html", _profile_context(db, user, saved=True), db=db, user=user)


@router.post("/profile/timezone")
def profile_timezone_update(
    request: Request,
    timezone: str = Form(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """Меняет часовой пояс — не чаще раза в 30 дней, и только на валидный пояс IANA."""
    if not is_valid_timezone(timezone):
        push_flash(request, "Неизвестный часовой пояс", "error")
        return render(request, "profile.html", _profile_context(db, user), db=db, user=user, status_code=400)

    if not can_change_timezone(user):
        push_flash(request, f"Часовой пояс можно менять не чаще раза в {TIMEZONE_CHANGE_COOLDOWN_DAYS} дней", "error")
        return render(request, "profile.html", _profile_context(db, user), db=db, user=user, status_code=400)

    user.timezone = timezone
    user.timezone_changed_at = datetime.now(dt_timezone.utc)
    db.add(user)
    db.commit()
    db.refresh(user)
    push_flash(request, f"Часовой пояс изменён на {timezone}")
    return render(request, "profile.html", _profile_context(db, user), db=db, user=user)
