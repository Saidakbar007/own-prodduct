"""
Ставки: поставить очки на выполнение привычки N дней подряд.
"""

from fastapi import APIRouter, Depends, Form, Request
from sqlmodel import Session

from app.auth import require_user
from app.database import get_session
from app.models import Habit, User
from app.services.bets import place_bet
from app.services.flash import push_flash

router = APIRouter()


@router.post("/habits/{habit_id}/bet")
def create_bet(
    habit_id: int,
    request: Request,
    stake_points: int = Form(...),
    target_days: int = Form(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """Создаёт ставку на привычку (очки списываются сразу)."""
    from app.routers.habits import habit_detail

    habit = db.get(Habit, habit_id)
    if habit and habit.uid == user.id and target_days > 0:
        bet = place_bet(db, user, habit, stake_points, target_days)
        if bet:
            push_flash(request, f"Ставка принята: {stake_points} очков на {target_days} дней подряд 🎲")
        else:
            push_flash(request, "Недостаточно очков для такой ставки")

    return habit_detail(habit_id, request, user, db)
