"""
Подсчёт streak (дней подряд с отметкой) по истории отметок.
"""

from datetime import date, timedelta


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
