"""
Страница достижений: все значки каталога, полученные — цветные, остальные — серые.
"""

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session, select

from app.auth import require_user
from app.database import get_session
from app.models import Achievement, User, UserAchievement
from app.rendering import render

router = APIRouter()


@router.get("/achievements")
def achievements_page(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    """Показывает весь каталог достижений с отметкой, что уже получено."""
    all_achievements = db.exec(select(Achievement).order_by(Achievement.id)).all()
    earned_ids = {
        ua.achievement_id
        for ua in db.exec(select(UserAchievement).where(UserAchievement.uid == user.id)).all()
    }

    items = [{"achievement": a, "earned": a.id in earned_ids} for a in all_achievements]

    return render(request, "achievements.html", {"user": user, "items": items}, db=db, user=user)
