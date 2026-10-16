"""
Подсчёт streak (дней подряд с отметкой) по истории отметок.
"""

from datetime import date, timedelta

from sqlmodel import Session, select


def calculate_streak(marked_dates: set[date]) -> int:
    """
    Считает текущую серию дней подряд с отметкой.
    Серия отсчитывается от самой последней отметки назад.
    Если последняя отметка была больше суток назад — серия считается прерванной (0).
    """
    if not marked_dates:
        return 0

    today = date.today()
    last_marked = max(marked_dates)

    if (today - last_marked).days > 1:
        return 0

    streak = 0
    day = last_marked
    while day in marked_dates:
        streak += 1
        day -= timedelta(days=1)

    return streak


def best_streak_for_user(db: Session, uid: int) -> int:
    """Лучший (максимальный) текущий streak среди всех привычек пользователя."""
    from app.models import Habit, HabitHistory

    habits = db.exec(select(Habit).where(Habit.uid == uid)).all()
    best = 0
    for habit in habits:
        history = db.exec(select(HabitHistory).where(HabitHistory.h_id == habit.id)).all()
        dates = {h.time.date() for h in history}
        best = max(best, calculate_streak(dates))
    return best
