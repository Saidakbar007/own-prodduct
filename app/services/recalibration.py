"""
Перекалибровка: если привычка выполнена (полностью, kind="done") 30 дней
подряд без единого пропуска/минимальной версии, сложность снижается на
одну ступень — привычка явно стала слишком лёгкой для текущего уровня.
"""

from datetime import date, timedelta

from sqlmodel import Session, select

from app.models import Habit, HabitHistory
from app.services.difficulty import difficulty_from_points, step_down
from app.services.points import points_for_habit_difficulty

RECALIBRATION_STREAK_DAYS = 30


def _last_n_days_all_done(db: Session, habit_id: int, n: int) -> bool:
    today = date.today()
    done_dates = {
        h.time.date()
        for h in db.exec(select(HabitHistory).where(HabitHistory.h_id == habit_id)).all()
        if h.kind == "done"
    }
    for i in range(n):
        if (today - timedelta(days=i)) not in done_dates:
            return False
    return True


def maybe_recalibrate(db: Session, habit: Habit) -> str | None:
    """
    Проверяет условие и, если нужно, снижает сложность привычки на ступень.
    Возвращает новое название сложности, если перекалибровка произошла, иначе None.
    """
    if habit.last_recalibration and (date.today() - habit.last_recalibration).days < RECALIBRATION_STREAK_DAYS:
        return None  # уже перекалибровали недавно — не делаем это каждый день подряд

    if not _last_n_days_all_done(db, habit.id, RECALIBRATION_STREAK_DAYS):
        return None

    current_difficulty = difficulty_from_points(habit.point)
    new_difficulty = step_down(current_difficulty)
    if new_difficulty == current_difficulty:
        return None  # уже easy — ниже некуда

    habit.point = points_for_habit_difficulty(new_difficulty)
    habit.last_recalibration = date.today()
    db.add(habit)
    db.commit()
    return new_difficulty
