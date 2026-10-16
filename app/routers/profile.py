"""
Профиль пользователя: вес, рост, семейное положение.
"""

from fastapi import APIRouter, Depends, Form, Request
from sqlmodel import Session

from app.auth import require_user
from app.database import get_session
from app.models import User
from app.rendering import render

router = APIRouter()


@router.get("/profile")
def profile_page(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    """Показывает текущие данные профиля."""
    return render(request, "profile.html", {"user": user, "saved": False}, db=db, user=user)


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
    return render(request, "profile.html", {"user": user, "saved": True}, db=db, user=user)
