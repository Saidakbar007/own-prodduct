"""
Страница статистики: очки, уровень, прогресс до следующего уровня,
графики (отметки за 30 дней, очки по неделям) и карточки.
"""

import json

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session, select

from app.auth import require_user
from app.database import get_session
from app.models import Level, User
from app.rendering import render
from app.services.levels import level_progress
from app.services.stats import checks_per_day, month_over_month, points_per_week, stats_cards

router = APIRouter()


@router.get("/stats")
def stats_page(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    """Показывает уровень, прогресс, графики и карточки со статистикой."""
    level = db.exec(select(Level).where(Level.uid == user.id)).first()
    if not level:
        level = Level(uid=user.id, point=0, name="Новичок")
        db.add(level)
        db.commit()
        db.refresh(level)

    progress = level_progress(level.point)

    checks_data = checks_per_day(db, user.id, days=30)
    points_data = points_per_week(db, user.id, weeks=8)
    cards = stats_cards(db, user.id)
    comparison = month_over_month(db, user.id)

    return render(
        request,
        "stats.html",
        {
            "user": user,
            "level": level,
            "hero_level": progress["level"],
            "hero_rank": progress["rank"],
            "next_rank": progress["next_rank"],
            "points_needed": (
                progress["xp_for_next_level"] - progress["xp_into_level"] if progress["xp_for_next_level"] else None
            ),
            "progress_percent": progress["percent"],
            "checks_labels_json": json.dumps([c["date"][5:] for c in checks_data]),
            "checks_values_json": json.dumps([c["count"] for c in checks_data]),
            "points_labels_json": json.dumps([p["label"] for p in points_data]),
            "points_values_json": json.dumps([p["points"] for p in points_data]),
            "cards": cards,
            "comparison": comparison,
        },
        db=db,
        user=user,
    )
