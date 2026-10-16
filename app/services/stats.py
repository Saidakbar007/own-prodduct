"""
Данные для страницы статистики: графики и карточки.
"""

from datetime import date, timedelta

from sqlmodel import Session, select

from app.models import Goal, Habit, HabitHistory, PointsLog


def checks_per_day(db: Session, uid: int, days: int = 30) -> list[dict]:
    """Количество отметок привычек по дням за последние N дней (для графика)."""
    habit_ids = [h.id for h in db.exec(select(Habit).where(Habit.uid == uid)).all()]
    counts = {}
    if habit_ids:
        history = db.exec(select(HabitHistory).where(HabitHistory.h_id.in_(habit_ids))).all()
        for entry in history:
            day = entry.time.date()
            counts[day] = counts.get(day, 0) + 1

    today = date.today()
    return [
        {"date": (today - timedelta(days=i)).isoformat(), "count": counts.get(today - timedelta(days=i), 0)}
        for i in range(days - 1, -1, -1)
    ]


def points_per_week(db: Session, uid: int, weeks: int = 8) -> list[dict]:
    """Сумма очков по неделям за последние N недель (для графика)."""
    logs = db.exec(select(PointsLog).where(PointsLog.uid == uid)).all()
    today = date.today()

    result = []
    for w in range(weeks - 1, -1, -1):
        week_end = today - timedelta(days=7 * w)
        week_start = week_end - timedelta(days=6)
        total = sum(
            log.points for log in logs if week_start <= log.time.date() <= week_end
        )
        result.append({"label": week_start.strftime("%d.%m"), "points": total})
    return result


def stats_cards(db: Session, uid: int) -> dict:
    """Карточки: лучшая серия, всего отметок, выполнено целей, % выполнения за неделю."""
    from app.services.streak import best_streak_for_user

    habits = db.exec(select(Habit).where(Habit.uid == uid)).all()
    habit_ids = [h.id for h in habits]

    total_checks = 0
    checks_this_week = 0
    if habit_ids:
        history = db.exec(select(HabitHistory).where(HabitHistory.h_id.in_(habit_ids))).all()
        total_checks = len(history)
        week_ago = date.today() - timedelta(days=6)
        checks_this_week = sum(1 for h in history if h.time.date() >= week_ago)

    goals_completed = len(
        db.exec(select(Goal).where(Goal.uid == uid, Goal.status == "completed")).all()
    )

    week_completion_percent = 0
    if habits:
        week_completion_percent = int(checks_this_week / (len(habits) * 7) * 100)

    return {
        "best_streak": best_streak_for_user(db, uid),
        "total_checks": total_checks,
        "goals_completed": goals_completed,
        "week_completion_percent": min(week_completion_percent, 100),
    }
