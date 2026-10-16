"""
AI-коуч: страница с советом на основе данных пользователя.
"""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.auth import require_user
from app.database import get_session
from app.models import Level, User
from app.services.coach import get_coach_advice
from app.services.streak import best_streak_for_user

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _advice_for(db: Session, user: User, question: str = None) -> str:
    level = db.exec(select(Level).where(Level.uid == user.id)).first()
    best_streak = best_streak_for_user(db, user.id)
    return get_coach_advice(
        habits_count=user.habits,
        best_streak=best_streak,
        level_name=level.name if level else "Новичок",
        points=level.point if level else 0,
        question=question,
    )


@router.get("/coach")
def coach_page(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    """Показывает совет коуча на основе текущих данных пользователя."""
    advice = _advice_for(db, user)
    return templates.TemplateResponse(request, "coach.html", {"user": user, "advice": advice, "question": None})


@router.post("/coach")
def coach_ask(
    request: Request,
    question: str = Form(None),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """Отвечает на вопрос пользователя (заглушка или Claude API, если есть ключ)."""
    advice = _advice_for(db, user, question)
    return templates.TemplateResponse(
        request, "coach.html", {"user": user, "advice": advice, "question": question}
    )
