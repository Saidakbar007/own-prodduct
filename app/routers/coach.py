"""
AI-коуч: страница с историей переписки (сохраняется в coach_messages).
"""

from fastapi import APIRouter, Depends, Form, Request
from sqlmodel import Session, select

from app.auth import require_user
from app.database import get_session
from app.models import CoachMessage, Level, User
from app.rendering import render
from app.services.coach import get_coach_advice
from app.services.streak import best_streak_for_user

router = APIRouter()


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


def _history(db: Session, user: User) -> list[CoachMessage]:
    return db.exec(
        select(CoachMessage).where(CoachMessage.uid == user.id).order_by(CoachMessage.time.asc())
    ).all()


@router.get("/coach")
def coach_page(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    """Показывает историю переписки с коучем; если она пуста — приветственный совет."""
    history = _history(db, user)
    if not history:
        advice = _advice_for(db, user)
        db.add(CoachMessage(uid=user.id, role="coach", text=advice))
        db.commit()
        history = _history(db, user)

    return render(request, "coach.html", {"user": user, "history": history}, db=db, user=user)


@router.post("/coach")
def coach_ask(
    request: Request,
    question: str = Form(None),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """Добавляет вопрос пользователя и ответ коуча в историю переписки."""
    if question:
        db.add(CoachMessage(uid=user.id, role="user", text=question))
        db.commit()

        advice = _advice_for(db, user, question)
        db.add(CoachMessage(uid=user.id, role="coach", text=advice))
        db.commit()

    history = _history(db, user)
    return render(request, "coach.html", {"user": user, "history": history}, db=db, user=user)
