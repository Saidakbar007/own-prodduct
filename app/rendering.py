"""
Общий рендеринг шаблонов: добавляет в контекст XP-бар (для шапки сайта)
и всплывающие уведомления (flash), чтобы не повторять это в каждом роуте.
"""

from typing import Optional

from fastapi import Request
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.models import Level, User
from app.services.flash import pop_flashes
from app.services.points import LEVEL_THRESHOLDS, next_level_info

templates = Jinja2Templates(directory="app/templates")


def _xp_context(db: Session, user: User) -> dict:
    level = db.exec(select(Level).where(Level.uid == user.id)).first()
    if not level:
        return {}

    next_info = next_level_info(level.point)
    current_threshold = 0
    for threshold, _name in LEVEL_THRESHOLDS:
        if level.point >= threshold:
            current_threshold = threshold

    if next_info:
        next_name, points_needed = next_info
        next_threshold = level.point + points_needed
        span = next_threshold - current_threshold
        percent = int(((level.point - current_threshold) / span) * 100) if span else 100
    else:
        next_name, points_needed, percent = None, None, 100

    return {
        "xp_level": level,
        "xp_percent": percent,
        "xp_next_name": next_name,
        "xp_points_needed": points_needed,
    }


def render(
    request: Request,
    name: str,
    context: Optional[dict] = None,
    db: Optional[Session] = None,
    user: Optional[User] = None,
    status_code: int = 200,
):
    """
    Рендерит шаблон, автоматически добавляя:
    - XP-бар в шапку (если передан db + user);
    - накопленные flash-уведомления (если передан request с активной сессией).
    """
    full_context = dict(context or {})

    if db is not None and user is not None:
        full_context.update(_xp_context(db, user))

    full_context["flashes"] = pop_flashes(request)

    return templates.TemplateResponse(request, name, full_context, status_code=status_code)
