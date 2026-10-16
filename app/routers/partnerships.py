"""
Напарник: предложить другу общую серию, принять (выбрав свою привычку) или отклонить.
"""

from fastapi import APIRouter, Depends, Form, Request
from sqlmodel import Session, select

from app.auth import require_user
from app.database import get_session
from app.models import Friend, Habit, Partnership, User
from app.rendering import render
from app.services.flash import push_flash

router = APIRouter()


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


@router.post("/habits/{habit_id}/partnership")
def propose_partnership(
    habit_id: int,
    request: Request,
    friend_login: str = Form(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """Предлагает другу стать напарником на этой привычке."""
    from app.routers.habits import habit_detail

    habit = db.get(Habit, habit_id)
    friend_user = db.exec(select(User).where(User.login == friend_login)).first()

    if habit and habit.uid == user.id and friend_user and _are_friends(db, user.id, friend_user.id):
        db.add(Partnership(uid_a=user.id, habit_id_a=habit_id, uid_b=friend_user.id, status="pending"))
        db.commit()
        push_flash(request, f"Предложение отправлено {friend_login} 🤝")
    else:
        push_flash(request, "Не удалось отправить предложение — проверь логин друга")

    return habit_detail(habit_id, request, user, db)


@router.get("/partnerships")
def my_partnerships(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    """Предложения напарника, адресованные мне (ожидают выбора привычки)."""
    incoming = db.exec(
        select(Partnership).where(Partnership.uid_b == user.id, Partnership.status == "pending")
    ).all()
    my_habits = db.exec(select(Habit).where(Habit.uid == user.id)).all()

    return render(
        request,
        "partnerships.html",
        {"user": user, "incoming": incoming, "my_habits": my_habits},
        db=db,
        user=user,
    )


@router.post("/partnerships/{partnership_id}/accept")
def accept_partnership(
    partnership_id: int,
    request: Request,
    habit_id: int = Form(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """Принимает предложение напарника, выбрав свою привычку для общей серии."""
    partnership = db.get(Partnership, partnership_id)
    habit = db.get(Habit, habit_id)

    if partnership and partnership.uid_b == user.id and partnership.status == "pending" and habit and habit.uid == user.id:
        partnership.habit_id_b = habit_id
        partnership.status = "active"
        db.add(partnership)
        db.commit()
        push_flash(request, "Теперь у вас общая серия 🤝🔥")

    return my_partnerships(request, user, db)


@router.post("/partnerships/{partnership_id}/decline")
def decline_partnership(
    partnership_id: int,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """Отклоняет предложение напарника."""
    partnership = db.get(Partnership, partnership_id)
    if partnership and partnership.uid_b == user.id and partnership.status == "pending":
        partnership.status = "declined"
        db.add(partnership)
        db.commit()

    return my_partnerships(request, user, db)
