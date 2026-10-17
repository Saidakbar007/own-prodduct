"""
Анти-сговор друзей: подтверждения другом имеют вес, а не считаются
поровну — ноль, если у подтверждающего низкий trust, и ×0.25, если пара
подозрительно подтверждает только друг друга (взаимная накрутка).
"""

from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.models import Habit, HabitConfirmation, HabitHistory, User

MUTUAL_PAIR_WINDOW_DAYS = 14
MUTUAL_PAIR_THRESHOLD = 0.8
LOW_TRUST_THRESHOLD = 40
MUTUAL_PAIR_WEIGHT = 0.25


def habit_owner_for_history(db: Session, history_id: int) -> int | None:
    """Владелец привычки, к которой относится конкретная запись истории."""
    history = db.get(HabitHistory, history_id)
    if not history:
        return None
    habit = db.get(Habit, history.h_id)
    return habit.uid if habit else None


def _confirmation_pairs_for(db: Session, uid: int, days: int) -> list[int]:
    """
    Список "второй стороны" для всех подтверждений, связанных с uid за
    последние `days` дней — и тех, что uid выдал сам, и тех, что получил.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    others = []

    given = db.exec(
        select(HabitConfirmation).where(HabitConfirmation.confirmer_uid == uid, HabitConfirmation.time >= cutoff)
    ).all()
    for c in given:
        owner = habit_owner_for_history(db, c.history_id)
        if owner is not None:
            others.append(owner)

    my_habit_ids = [h.id for h in db.exec(select(Habit).where(Habit.uid == uid)).all()]
    if my_habit_ids:
        my_history_ids = [
            h.id for h in db.exec(select(HabitHistory).where(HabitHistory.h_id.in_(my_habit_ids))).all()
        ]
        if my_history_ids:
            received = db.exec(
                select(HabitConfirmation).where(
                    HabitConfirmation.history_id.in_(my_history_ids), HabitConfirmation.time >= cutoff
                )
            ).all()
            others.extend(c.confirmer_uid for c in received)

    return others


def is_mutual_pair(db: Session, uid_a: int, uid_b: int, days: int = MUTUAL_PAIR_WINDOW_DAYS) -> bool:
    """
    ≥80% подтверждений, связанных с uid_a за последние N дней, — именно с
    uid_b (и наоборот) -> похоже на пару, подтверждающую только друг друга.
    """
    others = _confirmation_pairs_for(db, uid_a, days)
    if not others:
        return False
    matching = sum(1 for o in others if o == uid_b)
    return (matching / len(others)) >= MUTUAL_PAIR_THRESHOLD


def confirmation_weight(db: Session, confirmation: HabitConfirmation, owner_uid: int) -> float:
    """Вес конкретного подтверждения для расчёта trust score владельца отметки."""
    confirmer = db.get(User, confirmation.confirmer_uid)
    if not confirmer or confirmer.trust_score < LOW_TRUST_THRESHOLD:
        return 0.0
    if is_mutual_pair(db, owner_uid, confirmation.confirmer_uid):
        return MUTUAL_PAIR_WEIGHT
    return 1.0
