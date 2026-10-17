"""
Страница /boss: босс недели, группа пользователя (если есть), группы
друзей, к которым можно присоединиться, лента ударов.
"""

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session, select

from app.auth import require_user
from app.database import get_session
from app.models import Level, User
from app.rendering import render
from app.services.bosses import (
    BOSS_UNLOCK_HERO_LEVEL,
    BOSSES,
    active_group_for_user,
    boss_of_week,
    create_group,
    current_week_key,
    expire_stale_groups,
    group_members,
    hit_feed,
    join_group,
    joinable_groups_for_user,
)
from app.services.flash import push_flash
from app.services.game_assets import boss_image_url
from app.services.levels import level_progress

router = APIRouter()


def _hero_level(db: Session, user: User) -> int:
    level = db.exec(select(Level).where(Level.uid == user.id)).first()
    return level_progress(level.point if level else 0)["level"]


def _boss_context(db: Session, user: User) -> dict:
    expire_stale_groups(db)
    hero_level = _hero_level(db, user)
    week = current_week_key()
    boss_code = boss_of_week(week)
    group = active_group_for_user(db, user.id)

    members = []
    feed = []
    if group:
        for member in group_members(db, group.id):
            member_user = db.get(User, member.uid)
            members.append(member_user.login if member_user else "?")
        feed = hit_feed(db, group.id)

    return {
        "user": user,
        "hero_level": hero_level,
        "unlock_level": BOSS_UNLOCK_HERO_LEVEL,
        "unlocked": hero_level >= BOSS_UNLOCK_HERO_LEVEL,
        "boss_code": boss_code,
        "boss_name": BOSSES[boss_code],
        "boss_image_url": boss_image_url(boss_code),
        "group": group,
        "members": members,
        "feed": feed,
        "joinable_groups": [
            {"group": g, "boss_name": BOSSES[g.boss_code], "members": group_members(db, g.id)}
            for g in joinable_groups_for_user(db, user.id)
        ],
    }


@router.get("/boss")
def boss_page(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    return render(request, "boss.html", _boss_context(db, user), db=db, user=user)


@router.post("/boss/create")
def boss_create(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    _group, message = create_group(db, user, _hero_level(db, user))
    push_flash(request, message, "success" if _group else "error")
    return render(request, "boss.html", _boss_context(db, user), db=db, user=user)


@router.post("/boss/{group_id}/join")
def boss_join(
    group_id: int, request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)
):
    ok, message = join_group(db, user, group_id)
    push_flash(request, message, "success" if ok else "error")
    return render(request, "boss.html", _boss_context(db, user), db=db, user=user)
