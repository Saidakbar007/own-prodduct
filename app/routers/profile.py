"""
Профиль пользователя: вес, рост, семейное положение.
"""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from app.auth import require_user
from app.database import get_session
from app.models import User

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/profile")
def profile_page(request: Request, user: User = Depends(require_user)):
    """Показывает текущие данные профиля."""
    return templates.TemplateResponse(request, "profile.html", {"user": user, "saved": False})


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
    return templates.TemplateResponse(request, "profile.html", {"user": user, "saved": True})
