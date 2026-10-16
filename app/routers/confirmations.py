"""
Подтверждение отметки другом: "Подтвердить" (+бонус обоим) или "Правда?" (сомнение).
"""

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session, select

from app.auth import require_user
from app.database import get_session
from app.models import Friend, Habit, HabitConfirmation, HabitHistory, User
from app.rendering import render
from app.services.flash import push_flash
from app.services.points import award_points
from app.services.trust import refresh_trust_score

router = APIRouter()

OWNER_BONUS = 3
CONFIRMER_BONUS = 1


def _are_friends(db: Session, uid_a: int, uid_b: int) -> bool:
    return (
        db.exec(
            select(Friend).where(
                Friend.status == "accepted",
                ((Friend.uid == uid_a) & (Friend.friend_id == uid_b))
                | ((Friend.uid == uid_b) & (Friend.friend_id == uid_a)),
            )
        ).first()
        is not None
    )


@router.post("/confirmations/{history_id}/confirm")
def confirm_checkin(
    history_id: int,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """Друг подтверждает чужую отметку — бонус очков владельцу и подтверждающему."""
    from app.routers.friends import _friends_context

    entry = db.get(HabitHistory, history_id)
    habit = db.get(Habit, entry.h_id) if entry else None
    if not entry or not habit or habit.uid == user.id or not _are_friends(db, habit.uid, user.id):
        return render(
            request, "friends.html", _friends_context(db, user, "Нельзя подтвердить"), db=db, user=user, status_code=404
        )

    existing = db.exec(
        select(HabitConfirmation).where(
            HabitConfirmation.history_id == history_id, HabitConfirmation.confirmer_uid == user.id
        )
    ).first()
    if existing:
        from app.routers.friends import friends_list

        return friends_list(request, user, db)

    db.add(HabitConfirmation(history_id=history_id, confirmer_uid=user.id, status="confirmed"))
    db.commit()

    # Бонусы за подтверждение не масштабируются trust score: это социальный
    # сигнал доверия от другого человека, а не самоотчёт пользователя —
    # применять к нему тот же множитель было бы циклично.
    owner = db.get(User, habit.uid)
    award_points(db, owner, OWNER_BONUS, apply_trust=False)
    award_points(db, user, CONFIRMER_BONUS, apply_trust=False)
    refresh_trust_score(db, owner)
    push_flash(request, f"Подтверждено! +{CONFIRMER_BONUS} очка тебе, +{OWNER_BONUS} другу")

    from app.routers.friends import friends_list

    return friends_list(request, user, db)


@router.post("/confirmations/{history_id}/doubt")
def doubt_checkin(
    history_id: int,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """Друг выражает сомнение ('правда?') — без начисления очков."""
    entry = db.get(HabitHistory, history_id)
    habit = db.get(Habit, entry.h_id) if entry else None
    if entry and habit and habit.uid != user.id and _are_friends(db, habit.uid, user.id):
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
