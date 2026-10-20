"""
Подтверждение отметки другом: "Подтвердить" (+trust владельцу, +монеты
обоим, НИКОГДА +XP) или "Правда?" (сомнение). Анти-сговор: подтвердить
можно только отметку с фото, не чаще 3 раз в день и не чаще 1 раза в
день одному и тому же другу, и только если дружба старше 7 дней.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session, select

from app.auth import require_user
from app.database import get_session
from app.models import Friend, Habit, HabitConfirmation, HabitHistory, User
from app.rendering import render
from app.services.flash import push_flash
from app.services.trust import refresh_trust_score

router = APIRouter()

OWNER_COIN_BONUS = 3
CONFIRMER_COIN_BONUS = 1
MIN_FRIENDSHIP_DAYS = 7
MAX_CONFIRMATIONS_PER_DAY = 3
MAX_CONFIRMATIONS_PER_FRIEND_PER_DAY = 1


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _friendship(db: Session, uid_a: int, uid_b: int) -> Friend | None:
    return db.exec(
        select(Friend).where(
            Friend.status == "accepted",
            ((Friend.uid == uid_a) & (Friend.friend_id == uid_b))
            | ((Friend.uid == uid_b) & (Friend.friend_id == uid_a)),
        )
    ).first()


def _are_friends(db: Session, uid_a: int, uid_b: int) -> bool:
    return _friendship(db, uid_a, uid_b) is not None


def _friendship_old_enough(db: Session, uid_a: int, uid_b: int) -> bool:
    friend = _friendship(db, uid_a, uid_b)
    if not friend:
        return False
    started = friend.update_date or friend.created_date
    return (_now() - started).days >= MIN_FRIENDSHIP_DAYS


def _confirmations_today_by(db: Session, confirmer_uid: int) -> list[HabitConfirmation]:
    today_start = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    return db.exec(
        select(HabitConfirmation).where(
            HabitConfirmation.confirmer_uid == confirmer_uid,
            HabitConfirmation.status == "confirmed",
            HabitConfirmation.time >= today_start,
        )
    ).all()


@router.post("/confirmations/{history_id}/confirm")
def confirm_checkin(
    history_id: int,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """Друг подтверждает чужую отметку с фото — trust владельцу, монеты обоим."""
    from app.routers.friends import _friends_context, friends_list

    entry = db.get(HabitHistory, history_id)
    habit = db.get(Habit, entry.h_id) if entry else None
    owner = db.get(User, habit.uid) if habit else None

    # Тестовый аккаунт (/admin/sandbox) не может ни подтверждать, ни быть
    # подтверждённым — с обеих сторон (v6d, см. DECISIONS.md, п.19)
    if (
        not entry
        or not habit
        or not owner
        or habit.uid == user.id
        or user.is_test
        or owner.is_test
        or not _are_friends(db, habit.uid, user.id)
    ):
        return render(
            request, "friends.html", _friends_context(db, user, "Нельзя подтвердить"), db=db, user=user, status_code=404
        )

    if not entry.proof_path:
        return render(
            request,
            "friends.html",
            _friends_context(db, user, "Подтвердить можно только отметку с фото"),
            db=db,
            user=user,
            status_code=400,
        )

    if not _friendship_old_enough(db, habit.uid, user.id):
        return render(
            request,
            "friends.html",
            _friends_context(db, user, f"Подтверждать можно только друзьям дольше {MIN_FRIENDSHIP_DAYS} дней"),
            db=db,
            user=user,
            status_code=400,
        )

    existing = db.exec(
        select(HabitConfirmation).where(
            HabitConfirmation.history_id == history_id, HabitConfirmation.confirmer_uid == user.id
        )
    ).first()
    if existing:
        return friends_list(request, user, db)

    today_confirmations = _confirmations_today_by(db, user.id)
    if len(today_confirmations) >= MAX_CONFIRMATIONS_PER_DAY:
        return render(
            request,
            "friends.html",
            _friends_context(db, user, "Лимит подтверждений на сегодня исчерпан (3 в день)"),
            db=db,
            user=user,
            status_code=400,
        )

    same_friend_today = sum(
        1 for c in today_confirmations
        if _owner_of(db, c.history_id) == habit.uid
    )
    if same_friend_today >= MAX_CONFIRMATIONS_PER_FRIEND_PER_DAY:
        return render(
            request,
            "friends.html",
            _friends_context(db, user, "Этому другу сегодня уже подтверждали отметку"),
            db=db,
            user=user,
            status_code=400,
        )

    db.add(HabitConfirmation(history_id=history_id, confirmer_uid=user.id, status="confirmed"))
    db.commit()

    # Подтверждение даёт только trust и монеты — никогда XP (анти-сговор друзей).
    owner = db.get(User, habit.uid)
    owner.coins += OWNER_COIN_BONUS
    user.coins += CONFIRMER_COIN_BONUS
    db.add(owner)
    db.add(user)
    db.commit()
    refresh_trust_score(db, owner)
    push_flash(request, f"Подтверждено! +{CONFIRMER_COIN_BONUS} монета тебе, +{OWNER_COIN_BONUS} другу")

    return friends_list(request, user, db)


def _owner_of(db: Session, history_id: int) -> int | None:
    entry = db.get(HabitHistory, history_id)
    if not entry:
        return None
    habit = db.get(Habit, entry.h_id)
    return habit.uid if habit else None


@router.post("/confirmations/{history_id}/doubt")
def doubt_checkin(
    history_id: int,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """Друг выражает сомнение ('правда?') — без начисления чего-либо."""
    entry = db.get(HabitHistory, history_id)
    habit = db.get(Habit, entry.h_id) if entry else None
    owner = db.get(User, habit.uid) if habit else None
    if (
        entry
        and habit
        and owner
        and habit.uid != user.id
        and not user.is_test
        and not owner.is_test
        and _are_friends(db, habit.uid, user.id)
    ):
        existing = db.exec(
            select(HabitConfirmation).where(
                HabitConfirmation.history_id == history_id, HabitConfirmation.confirmer_uid == user.id
            )
        ).first()
        if not existing:
            db.add(HabitConfirmation(history_id=history_id, confirmer_uid=user.id, status="doubted"))
            db.commit()
        push_flash(request, "Ты выразил сомнение 🤔")

    from app.routers.friends import friends_list

    return friends_list(request, user, db)
