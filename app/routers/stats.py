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
from app.services.points import LEVEL_THRESHOLDS, next_level_info
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

    next_level = next_level_info(level.point)

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
            "next_name": next_name,
            "points_needed": points_needed,
            "progress_percent": progress_percent,
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
