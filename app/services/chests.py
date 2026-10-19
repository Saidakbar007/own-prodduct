"""
Сундук: награда за неделю без пропусков (каждый день — done/minimal) или
за победу над боссом недели (см. app/services/bosses.py). Редкость —
по весам 60/28/10/2% (common/rare/epic/legendary), trust >= 90 удваивает
шанс легендарного (см. DECISIONS.md, п.9).
"""

import random
from datetime import date, timedelta

from sqlmodel import Session, select

from app.models import Chest, Habit, HabitHistory, User
from app.services.coins import award_coins
from app.services.personas import has_harmony
from app.services.points import award_points
from app.services.shop import FREEZE_MAX_STOCK, RARITY_ORDER

RARITY_WEIGHTS = {"common": 60, "rare": 28, "epic": 10, "legendary": 2}
LEGENDARY_TRUST_THRESHOLD = 90


def _week_start(day: date) -> date:
    """Понедельник недели, в которую входит day."""
    return day - timedelta(days=day.weekday())


def roll_chest_rarity(trust_score: int) -> str:
    """
    Взвешенный выбор редкости сундука. trust >= 90 удваивает шанс
    легендарного (2% -> 4%), лишнее забирается у "обычного" (60% -> 58%) —
    остальные доли не трогаем (см. DECISIONS.md, п.9).
    """
    weights = dict(RARITY_WEIGHTS)
    if trust_score >= LEGENDARY_TRUST_THRESHOLD:
        extra = weights["legendary"]
        weights["legendary"] += extra
        weights["common"] -= extra

    roll = random.uniform(0, sum(weights.values()))
    cumulative = 0
    for rarity in RARITY_ORDER:
        cumulative += weights[rarity]
        if roll <= cumulative:
            return rarity
    return RARITY_ORDER[-1]


def _bump_rarity(rarity: str) -> str:
    """Поднимает редкость на ступень выше (common->rare->epic->legendary)."""
    i = RARITY_ORDER.index(rarity)
    return RARITY_ORDER[min(i + 1, len(RARITY_ORDER) - 1)]


def _apply_reward_for_rarity(db: Session, user: User, rarity: str) -> tuple[str, str]:
    """Начисляет награду по редкости. Возвращает (reward_type, reward_value) для записи в Chest."""
    if rarity == "common":
        award_points(db, user, 20)
        return "points", "20"

    if rarity == "rare":
        if user.freeze_stock < FREEZE_MAX_STOCK:
            user.freeze_stock += 1
            db.add(user)
            db.commit()
            return "freeze", "+1 заморозка в запас"
        award_points(db, user, 40)  # запас заморозок полон — не терять награду впустую
        return "points", "40"

    if rarity == "epic":
        award_points(db, user, 80)
        award_coins(db, user, 10)
        return "points", "80 XP + 10 монет"

    # legendary
    award_points(db, user, 150)
    award_coins(db, user, 30)
    return "badge", "Легендарная воля 🛡️ (+150 XP, +30 монет)"


def grant_chest(db: Session, user: User, week_start: date, habit_id: int = None, forced_rarity: str = None) -> Chest:
    """
    Выдаёт сундук со случайной редкостью (с учётом trust и "гармонии") и
    применяет его награду. Используется и для недельной серии привычки,
    и для победы над боссом (тогда habit_id=None). `forced_rarity` —
    только для песочницы /admin/sandbox, пропускает случайный бросок.
    """
    if forced_rarity:
        rarity = forced_rarity
    else:
        rarity = roll_chest_rarity(user.trust_score)
        if has_harmony(db, user.id):
            rarity = _bump_rarity(rarity)

    reward_type, reward_value = _apply_reward_for_rarity(db, user, rarity)

    chest = Chest(
        uid=user.id, habit_id=habit_id, week_start=week_start,
        reward_type=reward_type, reward_value=reward_value, rarity=rarity,
    )
    db.add(chest)
    db.commit()
    db.refresh(chest)
    return chest


def maybe_award_chest(db: Session, user: User, habit: Habit) -> Chest | None:
    """
    Если сегодня воскресенье и все 7 дней текущей недели отмечены (done/minimal),
    выдаёт сундук (один раз за неделю на привычку).
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

    return grant_chest(db, user, week_start, habit_id=habit.id)
