"""
Напарник: общая серия двух друзей на паре привычек.
Сгорает (status="broken"), если streak любого из двоих обнулился.
"""

from sqlmodel import Session, select

from app.models import HabitHistory, Partnership
from app.services.streak import calculate_streak


def _habit_streak(db: Session, habit_id: int) -> int:
    history = db.exec(select(HabitHistory).where(HabitHistory.h_id == habit_id)).all()
    dates = {h.time.date() for h in history if h.kind in ("done", "minimal")}
    return calculate_streak(dates)


def combined_streak(db: Session, partnership: Partnership) -> int:
    """Общая серия напарников = минимум из их streak (0, если партнёрство сгорело)."""
    if partnership.status != "active":
        return 0
    return min(_habit_streak(db, partnership.habit_id_a), _habit_streak(db, partnership.habit_id_b))


def evaluate_partnership(db: Session, partnership: Partnership) -> Partnership:
    """Проверяет, не сгорело ли партнёрство (у любого из двух streak стал 0)."""
    if partnership.status != "active":
        return partnership

    streak_a = _habit_streak(db, partnership.habit_id_a)
    streak_b = _habit_streak(db, partnership.habit_id_b)

    if streak_a == 0 or streak_b == 0:
        partnership.status = "broken"
        db.add(partnership)
        db.commit()

    return partnership


def evaluate_partnerships_for_habit(db: Session, habit_id: int) -> None:
    """Проверяет все активные партнёрства, где участвует эта привычка."""
    partnerships = db.exec(
        select(Partnership).where(
            Partnership.status == "active",
            (Partnership.habit_id_a == habit_id) | (Partnership.habit_id_b == habit_id),
        )
    ).all()
    for partnership in partnerships:
        evaluate_partnership(db, partnership)
