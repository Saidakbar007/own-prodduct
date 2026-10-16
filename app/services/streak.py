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
        dates = {h.time.date() for h in history if h.kind != "skip"}
        best = max(best, calculate_streak(dates))
    return best


def calculate_streak_with_freeze(
    done_dates: set[date],
    skip_dates: set[date],
    bonus_freezes: dict[str, int] = None,
    max_freezes_per_week: int = 2,
    today: date = None,
) -> dict:
    """
    Streak с учётом заморозки и честных пропусков.

    - "done"/"minimal" дни увеличивают серию;
    - честный пропуск ("Не сделал") не увеличивает серию, но и не обрывает её;
    - до max_freezes_per_week дней без ЛЮБОЙ отметки за календарную неделю
      не обрывают серию (видно, сколько заморозок осталось на эту неделю);
    - BonusFreeze (из сундука) увеличивает лимит заморозок для конкретной недели.

    `today` можно передать явно (для тестов) — по умолчанию date.today().
    Возвращает {"streak": int, "freezes_left": int}.
    """
    bonus_freezes = bonus_freezes or {}
    today = today or date.today()
    streak = 0
    freezes_used_by_week: dict = {}
    day = today

    all_dates = done_dates | skip_dates
    earliest = min(all_dates) if all_dates else None

    while True:
        if day in done_dates:
            streak += 1
            day -= timedelta(days=1)
            continue
        if day in skip_dates:
            day -= timedelta(days=1)
            continue

        # Не тратим заморозки на дни до самой первой отметки — привычки тогда
        # просто ещё не существовало, это не настоящий пропуск.
        if earliest is None or day < earliest:
            break

        week_key = _week_key(day)
        limit = max_freezes_per_week + bonus_freezes.get(week_key, 0)
        used = freezes_used_by_week.get(week_key, 0)
        if used < limit:
            freezes_used_by_week[week_key] = used + 1
            day -= timedelta(days=1)
            continue
        break

    current_week_key = _week_key(today)
    current_limit = max_freezes_per_week + bonus_freezes.get(current_week_key, 0)
    freezes_left = current_limit - freezes_used_by_week.get(current_week_key, 0)

    return {"streak": streak, "freezes_left": max(freezes_left, 0)}


def _week_key(day: date) -> str:
    """Ключ календарной недели в формате ISO, например '2026-W03'."""
    iso_year, iso_week, _ = day.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def consecutive_run_from(done_dates: set[date], start: date, today: date) -> tuple[int, bool]:
    """
    Длина подряд идущих дней выполнения с start по today (без заморозки — для ставок).
    Возвращает (длина серии, прервана ли серия).
    """
    length = 0
    day = start
    while day <= today:
        if day in done_dates:
            length += 1
            day += timedelta(days=1)
        else:
            return length, True
    return length, False
