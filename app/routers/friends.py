"""
Друзья: заявка → принятие/отклонение, прогресс друга (уровень и streak).
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, Request
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.auth import require_user
from app.database import get_session
from app.models import Friend, Level, User
from app.services.streak import best_streak_for_user

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _friend_card(db: Session, user_id: int) -> dict:
    """Публичные данные о прогрессе пользователя: уровень + лучший streak."""
    friend_user = db.get(User, user_id)
    level = db.exec(select(Level).where(Level.uid == user_id)).first()
    return {
        "user": friend_user,
        "level_name": level.name if level else "Новичок",
        "points": level.point if level else 0,
        "streak": best_streak_for_user(db, user_id),
    }


def _friends_context(db: Session, user: User, error: str = None) -> dict:
    accepted = db.exec(
        select(Friend).where(
            Friend.status == "accepted",
            (Friend.uid == user.id) | (Friend.friend_id == user.id),
        )
    ).all()
    friend_ids = [f.friend_id if f.uid == user.id else f.uid for f in accepted]
    friends = [_friend_card(db, fid) for fid in friend_ids]

    incoming = db.exec(
        select(Friend).where(Friend.friend_id == user.id, Friend.status == "pending")
    ).all()
    outgoing = db.exec(
        select(Friend).where(Friend.uid == user.id, Friend.status == "pending")
    ).all()

    return {
        "user": user,
        "friends": friends,
        "incoming": incoming,
        "outgoing": outgoing,
        "error": error,
    }


@router.get("/friends")
def friends_list(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    """Список друзей, входящих и исходящих заявок."""
    return templates.TemplateResponse(request, "friends.html", _friends_context(db, user))


@router.post("/friends/request")
def send_request(
    request: Request,
    login: str = Form(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """Отправляет заявку в друзья по логину."""
    target = db.exec(select(User).where(User.login == login)).first()

    if not target or target.id == user.id:
        return templates.TemplateResponse(
            request, "friends.html", _friends_context(db, user, "Пользователь не найден"), status_code=404
        )

    existing = db.exec(
        select(Friend).where(
            ((Friend.uid == user.id) & (Friend.friend_id == target.id))
            | ((Friend.uid == target.id) & (Friend.friend_id == user.id))
        )
    ).first()
    if existing:
        return templates.TemplateResponse(
            request, "friends.html", _friends_context(db, user, "Заявка уже существует или вы уже друзья"), status_code=400
        )

    db.add(Friend(uid=user.id, friend_id=target.id, status="pending"))
    db.commit()
    return templates.TemplateResponse(request, "friends.html", _friends_context(db, user))


@router.post("/friends/{friend_id}/accept")
def accept_request(
    friend_id: int,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """Принимает заявку в друзья. Принять может только адресат заявки."""
    friend = db.get(Friend, friend_id)
    if friend and friend.friend_id == user.id and friend.status == "pending":
        friend.status = "accepted"
        friend.update_date = _now()
        db.add(friend)
        db.commit()
    return templates.TemplateResponse(request, "friends.html", _friends_context(db, user))


@router.post("/friends/{friend_id}/decline")
def decline_request(
    friend_id: int,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """Отклоняет заявку в друзья. Отклонить может только адресат заявки."""
    friend = db.get(Friend, friend_id)
    if friend and friend.friend_id == user.id and friend.status == "pending":
        friend.status = "declined"
        friend.update_date = _now()
        db.add(friend)
        db.commit()
    return templates.TemplateResponse(request, "friends.html", _friends_context(db, user))
