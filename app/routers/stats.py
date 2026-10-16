"""
Страница статистики: очки, уровень, прогресс до следующего уровня.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.auth import require_user
from app.database import get_session
from app.models import Level, User
from app.services.points import LEVEL_THRESHOLDS, next_level_info

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/stats")
def stats_page(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    """Показывает текущий уровень пользователя и прогресс до следующего."""
    level = db.exec(select(Level).where(Level.uid == user.id)).first()
    if not level:
        level = Level(uid=user.id, point=0, name="Новичок")
        db.add(level)
        db.commit()
        db.refresh(level)

    next_level = next_level_info(level.point)

    # Текущий порог — для прогресс-бара (сколько % пройдено до следующего уровня)
    current_threshold = 0
    for threshold, _name in LEVEL_THRESHOLDS:
        if level.point >= threshold:
            current_threshold = threshold

    if next_level:
        next_name, points_needed = next_level
        next_threshold = level.point + points_needed
        span = next_threshold - current_threshold
        progress_percent = int(((level.point - current_threshold) / span) * 100) if span else 100
    else:
        next_name, points_needed, progress_percent = None, None, 100

    return templates.TemplateResponse(
        request,
        "stats.html",
        {
            "user": user,
            "level": level,
            "next_name": next_name,
            "points_needed": points_needed,
            "progress_percent": progress_percent,
        },
    )
