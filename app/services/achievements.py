"""
Достижения: каталог + проверка условий + выдача пользователю.
С v6b часть достижений идёт в 3 тира (бронза/серебро/золото) — см.
DECISIONS.md, п.11. Старые коды (до v6b) не переименованы, чтобы не
терять историю уже выданных достижений — только дотегованы category/tier.
"""

from datetime import timedelta

from sqlmodel import Session, select

from app.models import (
    Achievement,
    Friend,
    Goal,
    Habit,
    HabitConfirmation,
    HabitHistory,
    User,
    UserAchievement,
)
from app.services.coins import award_coins, coins_for_achievement
from app.services.streak import best_streak_for_user

# Каталог достижений: код, название, описание, иконка, категория, тир (bronze/silver/gold/None)
CATALOG = [
    ("first_habit", "Первая привычка", "Создай свою первую привычку", "🌱", "milestone", None),
    ("first_goal_done", "Первая цель выполнена", "Заверши свою первую цель", "🎯", "goals", "bronze"),
    ("first_friend", "Первый друг", "Добавь первого друга", "🤝", "milestone", None),
    ("checks_100", "100 отметок", "Сделай 100 отметок привычек", "💯", "milestone", None),
    # Серии (бронза/серебро/золото) — 7/30/100 дней подряд
    ("streak_7", "Серия 7 дней", "Отметь привычку 7 дней подряд", "🔥", "streak", "bronze"),
    ("streak_30", "Серия 30 дней", "Отметь привычку 30 дней подряд", "🏅", "streak", "silver"),
    ("streak_100", "Серия 100 дней", "Отметь привычку 100 дней подряд", "👑", "streak", "gold"),
    # Сфера — любая личность достигла уровня 5/10/20
    ("sphere_bronze", "Пробуждение силы", "Любая личность достигла 5-го уровня", "🌟", "sphere", "bronze"),
    ("sphere_silver", "Растущая сила", "Любая личность достигла 10-го уровня", "💫", "sphere", "silver"),
    ("sphere_gold", "Пик силы", "Любая личность достигла 20-го уровня", "✨", "sphere", "gold"),
    # Честность — подтверждённые другом отметки (с фото) — 25/100/300
    ("honesty_bronze", "Честный путь", "25 отметок подтвердили друзья", "🛡️", "honesty", "bronze"),
    ("honesty_silver", "Проверенная воля", "100 отметок подтвердили друзья", "🛡️", "honesty", "silver"),
    ("honesty_gold", "Безупречная честность", "300 отметок подтвердили друзья", "🛡️", "honesty", "gold"),
    # Боссы — побед в группе — 1/5/20
    ("boss_bronze", "Первая победа", "Победи 1 босса недели", "⚔️", "boss", "bronze"),
    ("boss_silver", "Охотник на боссов", "Победи 5 боссов недели", "⚔️", "boss", "silver"),
    ("boss_gold", "Истребитель боссов", "Победи 20 боссов недели", "⚔️", "boss", "gold"),
    # Цели — завершённые цели — 1/5/20 (bronze = уже существующий first_goal_done)
    ("goals_silver", "Целеустремлённый", "Заверши 5 целей", "🎯", "goals", "silver"),
    ("goals_gold", "Мастер целей", "Заверши 20 целей", "🎯", "goals", "gold"),
    # Возвращения — отметка после пропуска — 1/5/15
    ("comeback_bronze", "Возвращение", "Вернись к привычке после пропуска", "🔄", "comeback", "bronze"),
    ("comeback_silver", "Не сдаёшься", "Вернись к привычке после пропуска 5 раз", "🔄", "comeback", "silver"),
    ("comeback_gold", "Непобедимый дух", "Вернись к привычке после пропуска 15 раз", "🔄", "comeback", "gold"),
    # Личности — все 5 на стадии 5
    ("all_personas_stage5", "Полный расцвет", "Все 5 личностей достигли стадии 5", "🏆", "personas", None),
]


def ensure_achievements_seeded(db: Session) -> None:
    """Заполняет/дотегует каталог достижений (безопасно перезапускать)."""
    for code, name, description, icon, category, tier in CATALOG:
        existing = db.exec(select(Achievement).where(Achievement.code == code)).first()
        if existing:
            existing.category = category
            existing.tier = tier
            db.add(existing)
        else:
            db.add(Achievement(code=code, name=name, description=description, icon=icon, category=category, tier=tier))
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


def _award(db: Session, user: User, code: str) -> Achievement | None:
    achievement = db.exec(select(Achievement).where(Achievement.code == code)).first()
    if not achievement or _has(db, user.id, code):
        return None
    db.add(UserAchievement(uid=user.id, achievement_id=achievement.id))
    db.commit()
    award_coins(db, user, coins_for_achievement(db, code))
    return achievement


def _total_checks(db: Session, uid: int) -> int:
    habit_ids = [h.id for h in db.exec(select(Habit).where(Habit.uid == uid)).all()]
    if not habit_ids:
        return 0
    return len(
        db.exec(select(HabitHistory).where(HabitHistory.h_id.in_(habit_ids))).all()
    )


def _goal_completions_count(db: Session, uid: int) -> int:
    return len(db.exec(select(Goal).where(Goal.uid == uid, Goal.status == "completed")).all())


def _confirmed_marks_count(db: Session, uid: int) -> int:
    """Сколько СВОИХ отметок (done/minimal) реально подтвердили друзья (см. DECISIONS.md, п.11)."""
    habit_ids = [h.id for h in db.exec(select(Habit).where(Habit.uid == uid)).all()]
    if not habit_ids:
        return 0
    entry_ids = [
        e.id
        for e in db.exec(
            select(HabitHistory).where(HabitHistory.h_id.in_(habit_ids), HabitHistory.kind.in_(("done", "minimal")))
        ).all()
    ]
    if not entry_ids:
        return 0
    confirmed = db.exec(
        select(HabitConfirmation).where(
            HabitConfirmation.history_id.in_(entry_ids), HabitConfirmation.status == "confirmed"
        )
    ).all()
    return len({c.history_id for c in confirmed})


def _comeback_count(db: Session, uid: int) -> int:
    """
    Отметки после пропуска: done/minimal в день, когда за ПРЕДЫДУЩИЙ
    календарный день по этой же привычке не было вообще никакой отметки
    — и до этого пропуска уже была хоть какая-то активность (иначе это
    просто первая отметка, а не "возврат").
    """
    habits = db.exec(select(Habit).where(Habit.uid == uid)).all()
    total = 0
    for habit in habits:
        entries = db.exec(select(HabitHistory).where(HabitHistory.h_id == habit.id)).all()
        all_dates = {e.time.date() for e in entries}
        done_dates = {e.time.date() for e in entries if e.kind in ("done", "minimal")}
        for d in done_dates:
            prev_day = d - timedelta(days=1)
            earlier_activity_exists = any(x < prev_day for x in all_dates)
            if prev_day not in all_dates and earlier_activity_exists:
                total += 1
    return total


def _max_sphere_level(db: Session, uid: int) -> int:
    from app.services.spheres import all_spheres_progress

    return max((s["level"] for s in all_spheres_progress(db, uid)), default=0)


def _all_personas_at_stage5(db: Session, uid: int) -> bool:
    from app.services.personas import persona_profile

    return all(p["stage"] == 5 for p in persona_profile(db, uid))


def check_and_award_achievements(db: Session, user: User) -> list[Achievement]:
    """Проверяет все условия и выдаёт новые достижения. Возвращает список новых."""
    newly_earned = []

    if user.habits >= 1:
        a = _award(db, user, "first_habit")
        if a:
            newly_earned.append(a)

    best_streak = best_streak_for_user(db, user.id)
    if best_streak >= 7:
        a = _award(db, user, "streak_7")
        if a:
            newly_earned.append(a)
    if best_streak >= 30:
        a = _award(db, user, "streak_30")
        if a:
            newly_earned.append(a)

    if best_streak >= 100:
        a = _award(db, user, "streak_100")
        if a:
            newly_earned.append(a)

    goal_completions = _goal_completions_count(db, user.id)
    if goal_completions >= 1:
        a = _award(db, user, "first_goal_done")
        if a:
            newly_earned.append(a)
    if goal_completions >= 5:
        a = _award(db, user, "goals_silver")
        if a:
            newly_earned.append(a)
    if goal_completions >= 20:
        a = _award(db, user, "goals_gold")
        if a:
            newly_earned.append(a)

    has_friend = db.exec(
        select(Friend).where(
            Friend.status == "accepted",
            (Friend.uid == user.id) | (Friend.friend_id == user.id),
        )
    ).first()
    if has_friend:
        a = _award(db, user, "first_friend")
        if a:
            newly_earned.append(a)

    if _total_checks(db, user.id) >= 100:
        a = _award(db, user, "checks_100")
        if a:
            newly_earned.append(a)

    max_sphere_level = _max_sphere_level(db, user.id)
    for threshold, code in ((5, "sphere_bronze"), (10, "sphere_silver"), (20, "sphere_gold")):
        if max_sphere_level >= threshold:
            a = _award(db, user, code)
            if a:
                newly_earned.append(a)

    confirmed_marks = _confirmed_marks_count(db, user.id)
    for threshold, code in ((25, "honesty_bronze"), (100, "honesty_silver"), (300, "honesty_gold")):
        if confirmed_marks >= threshold:
            a = _award(db, user, code)
            if a:
                newly_earned.append(a)

    from app.services.bosses import boss_victories_count

    boss_wins = boss_victories_count(db, user.id)
    for threshold, code in ((1, "boss_bronze"), (5, "boss_silver"), (20, "boss_gold")):
        if boss_wins >= threshold:
            a = _award(db, user, code)
            if a:
                newly_earned.append(a)

    comebacks = _comeback_count(db, user.id)
    for threshold, code in ((1, "comeback_bronze"), (5, "comeback_silver"), (15, "comeback_gold")):
        if comebacks >= threshold:
            a = _award(db, user, code)
            if a:
                newly_earned.append(a)

    if _all_personas_at_stage5(db, user.id):
        a = _award(db, user, "all_personas_stage5")
        if a:
            newly_earned.append(a)

    return newly_earned
