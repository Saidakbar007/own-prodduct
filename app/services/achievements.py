"""
Достижения (v2): каталог + проверка условий + выдача пользователю.
"""

from sqlmodel import Session, select

from app.models import (
    Achievement,
    Friend,
    Goal,
    Habit,
    HabitHistory,
    User,
    UserAchievement,
)
from app.services.streak import best_streak_for_user

# Каталог достижений: код → (название, описание, иконка)
CATALOG = [
    ("first_habit", "Первая привычка", "Создай свою первую привычку", "🌱"),
    ("streak_7", "Серия 7 дней", "Отметь привычку 7 дней подряд", "🔥"),
    ("streak_30", "Серия 30 дней", "Отметь привычку 30 дней подряд", "🏅"),
    ("first_goal_done", "Первая цель выполнена", "Заверши свою первую цель", "🎯"),
    ("first_friend", "Первый друг", "Добавь первого друга", "🤝"),
    ("checks_100", "100 отметок", "Сделай 100 отметок привычек", "💯"),
]


def ensure_achievements_seeded(db: Session) -> None:
    """Заполняет каталог достижений, если он пуст (безопасно перезапускать)."""
    for code, name, description, icon in CATALOG:
        existing = db.exec(select(Achievement).where(Achievement.code == code)).first()
        if not existing:
            db.add(Achievement(code=code, name=name, description=description, icon=icon))
    db.commit()


def _has(db: Session, uid: int, code: str) -> bool:
    achievement = db.exec(select(Achievement).where(Achievement.code == code)).first()
    if not achievement:
        return True  # каталог не заполнен — не выдаём, чтобы не упасть
    return (
        db.exec(
            select(UserAchievement).where(
                UserAchievement.uid == uid, UserAchievement.achievement_id == achievement.id
            )
        ).first()
        is not None
    )


def _award(db: Session, uid: int, code: str) -> Achievement | None:
    achievement = db.exec(select(Achievement).where(Achievement.code == code)).first()
    if not achievement or _has(db, uid, code):
        return None
    db.add(UserAchievement(uid=uid, achievement_id=achievement.id))
    db.commit()
    return achievement


def _total_checks(db: Session, uid: int) -> int:
    habit_ids = [h.id for h in db.exec(select(Habit).where(Habit.uid == uid)).all()]
    if not habit_ids:
        return 0
    return len(
        db.exec(select(HabitHistory).where(HabitHistory.h_id.in_(habit_ids))).all()
    )


def check_and_award_achievements(db: Session, user: User) -> list[Achievement]:
    """Проверяет все условия и выдаёт новые достижения. Возвращает список новых."""
    newly_earned = []

    if user.habits >= 1:
        a = _award(db, user.id, "first_habit")
        if a:
            newly_earned.append(a)

    best_streak = best_streak_for_user(db, user.id)
    if best_streak >= 7:
        a = _award(db, user.id, "streak_7")
        if a:
            newly_earned.append(a)
    if best_streak >= 30:
        a = _award(db, user.id, "streak_30")
        if a:
            newly_earned.append(a)

    done_goal = db.exec(
        select(Goal).where(Goal.uid == user.id, Goal.status == "completed")
    ).first()
    if done_goal:
        a = _award(db, user.id, "first_goal_done")
        if a:
            newly_earned.append(a)

    has_friend = db.exec(
        select(Friend).where(
            Friend.status == "accepted",
            (Friend.uid == user.id) | (Friend.friend_id == user.id),
        )
    ).first()
    if has_friend:
        a = _award(db, user.id, "first_friend")
        if a:
            newly_earned.append(a)

    if _total_checks(db, user.id) >= 100:
        a = _award(db, user.id, "checks_100")
        if a:
            newly_earned.append(a)

    return newly_earned
