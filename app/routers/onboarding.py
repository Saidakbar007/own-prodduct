"""
Короткий онбординг для нового пользователя: зачем приложение -> создай
мечту -> добавь первую привычку -> готово. Пропускаем на любом шаге.
"""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session

from app.auth import require_user
from app.database import get_session
from app.models import Goal, Habit, User
from app.rendering import render
from app.services.points import points_for_habit_difficulty

router = APIRouter()


@router.get("/onboarding")
def onboarding_intro(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    """Шаг 1: зачем это приложение."""
    return render(request, "onboarding.html", {"user": user, "step": 1}, db=db, user=user)


@router.get("/onboarding/dream")
def onboarding_dream_page(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    """Шаг 2: создать мечту."""
    return render(request, "onboarding.html", {"user": user, "step": 2}, db=db, user=user)


@router.post("/onboarding/dream")
def onboarding_dream_submit(
    request: Request,
    name: str = Form(None),
    description: str = Form(None),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """Создаёт мечту (если имя введено) и переходит к шагу про привычку."""
    if name:
        db.add(Goal(uid=user.id, name=name, description=description, parent_id=None))
        user.goals += 1
        db.add(user)
        db.commit()
    return RedirectResponse("/onboarding/habit", status_code=303)


@router.get("/onboarding/habit")
def onboarding_habit_page(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    """Шаг 3: добавить первую привычку."""
    return render(request, "onboarding.html", {"user": user, "step": 3}, db=db, user=user)


@router.post("/onboarding/habit")
def onboarding_habit_submit(
    request: Request,
    name: str = Form(None),
    difficulty: str = Form("medium"),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """Создаёт первую привычку (если имя введено) и переходит к финалу."""
    if name:
        db.add(Habit(uid=user.id, name=name, point=points_for_habit_difficulty(difficulty), story_point=1.0))
        user.habits += 1
        db.add(user)
        db.commit()
    return RedirectResponse("/onboarding/done", status_code=303)


@router.get("/onboarding/done")
def onboarding_done(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    """Шаг 4: готово."""
    return render(request, "onboarding.html", {"user": user, "step": 4}, db=db, user=user)
