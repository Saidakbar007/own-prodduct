"""
Общий рендеринг шаблонов: добавляет в контекст XP-бар (для шапки сайта)
и всплывающие уведомления (flash), чтобы не повторять это в каждом роуте.
"""

from typing import Optional

from fastapi import Request
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.models import Level, User
from app.services.admin import is_admin
from app.services.flash import pop_flashes
from app.services.levels import level_progress

templates = Jinja2Templates(directory="app/templates")


def _xp_context(db: Session, user: User) -> dict:
    level = db.exec(select(Level).where(Level.uid == user.id)).first()
    if not level:
        return {}

    progress = level_progress(level.point)

    return {
        "xp_level": level,
        "xp_percent": progress["percent"],
        "xp_hero_level": progress["level"],
        "xp_rank": progress["rank"],
        "xp_stage": progress["stage"],
        "xp_into_level": progress["xp_into_level"],
        "xp_for_next_level": progress["xp_for_next_level"],
        "xp_next_rank": progress["next_rank"],
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

    full_context.setdefault("is_admin", is_admin(user))
    full_context["flashes"] = pop_flashes(request)

    return templates.TemplateResponse(request, name, full_context, status_code=status_code)
