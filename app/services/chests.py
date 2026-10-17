"""
Сундук: случайная награда за неделю без пропусков (каждый день — done/minimal).
"""

import random
from datetime import date, timedelta

from sqlmodel import Session, select

from app.models import BonusFreeze, Chest, Habit, HabitHistory, User
from app.services.personas import has_harmony
from app.services.points import award_points
from app.services.streak import _week_key

POINTS_TIERS = [20, 30, 50]

# Лестница "силы" награды сундука: badge < freeze < points (см. DECISIONS.md, п.2)
REWARD_TIER_ORDER = ["badge", "freeze", "points"]


def _week_start(day: date) -> date:
    """Понедельник недели, в которую входит day."""
    return day - timedelta(days=day.weekday())


def _bump_points_tier(value: int) -> int:
    """Поднимает размер очкового тира на ступень (20->30->50, 50 — уже максимум)."""
    if value in POINTS_TIERS:
        i = POINTS_TIERS.index(value)
        if i + 1 < len(POINTS_TIERS):
            return POINTS_TIERS[i + 1]
    return value


def maybe_award_chest(db: Session, user: User, habit: Habit) -> Chest | None:
    """
    Если сегодня воскресенье и все 7 дней текущей недели отмечены (done/minimal),
    выдаёт случайную награду (один раз за неделю на привычку).
    """
    today = date.today()
    if today.weekday() != 6:  # только в воскресенье — неделя считается завершённой
        return None

    week_start = _week_start(today)
    already = db.exec(
        select(Chest).where(
            Chest.uid == user.id, Chest.habit_id == habit.id, Chest.week_start == week_start
        )
    ).first()
    if already:
        return None

    history = db.exec(select(HabitHistory).where(HabitHistory.h_id == habit.id)).all()
    done_dates = {h.time.date() for h in history if h.kind in ("done", "minimal")}
    week_days = {week_start + timedelta(days=i) for i in range(7)}
    if not week_days.issubset(done_dates):
        return None

    reward_type = random.choice(["points", "points", "freeze", "badge"])  # очки чаще выпадают
    value = random.choice(POINTS_TIERS) if reward_type == "points" else None

    if has_harmony(db, user.id):
        # "Гармония" (все 5 личностей активны за неделю) поднимает награду сундука
        # на ступень выше по лестнице badge < freeze < points (см. DECISIONS.md, п.2)
        tier_index = REWARD_TIER_ORDER.index(reward_type)
        if tier_index + 1 < len(REWARD_TIER_ORDER):
            reward_type = REWARD_TIER_ORDER[tier_index + 1]
            if reward_type == "points":
                value = POINTS_TIERS[-1]
        elif reward_type == "points":
            value = _bump_points_tier(value)

    if reward_type == "points":
        award_points(db, user, value)
        reward_value = str(value)
    elif reward_type == "freeze":
        next_week_key = _week_key(today + timedelta(days=1))
        bonus = db.exec(
            select(BonusFreeze).where(BonusFreeze.uid == user.id, BonusFreeze.week_key == next_week_key)
        ).first()
        if bonus:
            bonus.amount += 1
            db.add(bonus)
        else:
            db.add(BonusFreeze(uid=user.id, week_key=next_week_key, amount=1))
        db.commit()
        reward_value = "+1 заморозка на следующую неделю"
    else:
        reward_value = "Железная воля 🛡️"

    chest = Chest(uid=user.id, habit_id=habit.id, week_start=week_start, reward_type=reward_type, reward_value=reward_value)
    db.add(chest)
    db.commit()
    db.refresh(chest)
    return chest
