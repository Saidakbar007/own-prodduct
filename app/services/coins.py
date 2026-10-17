"""
Монеты — отдельная валюта от XP (появилась в v5 для подтверждений друзей,
в v6a расширена на привычки/задания/достижения). За монеты НЕЛЬЗЯ купить
XP, уровни или место в рейтинге — только магазин (см. app/services/shop.py);
рейтинг друзей и так считается по % выполнения + streak, не по XP/монетам.
"""

from sqlmodel import Session, select

from app.models import User

HABIT_COINS = {"easy": 1, "medium": 2, "hard": 4}
PROOF_PHOTO_BONUS = 1
DAILY_TASK_COINS = 3
DAILY_TASK_ALL_THREE_BONUS = 5

# Монеты за тир достижения (v6b) — bronze/silver/gold, см. DECISIONS.md, п.11.
TIER_COINS = {"bronze": 20, "silver": 50, "gold": 100}

# Достижения без тира (одиночные, появились до v6b) сохраняют старые
# фиксированные суммы, чтобы их награда не изменилась ретроактивно.
LEGACY_ACHIEVEMENT_COINS = {"first_habit": 20, "first_friend": 20, "checks_100": 100}

TRUST_LOW_THRESHOLD = 40
TRUST_HIGH_THRESHOLD = 80
HARMONY_COIN_BONUS = 0.10


def coin_trust_multiplier(trust_score: int) -> float:
    """<40 -> x0.5, 40-79 -> x1.0, 80+ -> x1.2 (отдельно от множителя XP)."""
    if trust_score < TRUST_LOW_THRESHOLD:
        return 0.5
    if trust_score < TRUST_HIGH_THRESHOLD:
        return 1.0
    return 1.2


def award_coins(db: Session, user: User, amount: int, apply_trust: bool = True, apply_harmony: bool = True) -> int:
    """
    Начисляет монеты с учётом trust-множителя и +10% за "гармонию" (все 5
    личностей активны за неделю). Возвращает реально начисленное количество.
    """
    if amount <= 0:
        return 0

    multiplier = 1.0
    if apply_trust:
        multiplier *= coin_trust_multiplier(user.trust_score)
    if apply_harmony:
        from app.services.personas import has_harmony

        if has_harmony(db, user.id):
            multiplier *= 1 + HARMONY_COIN_BONUS

    awarded = round(amount * multiplier)
    user.coins += awarded
    db.add(user)
    db.commit()
    return awarded


def coins_for_achievement(db: Session, code: str) -> int:
    """Монеты по тиру достижения (bronze/silver/gold); для нетировых — старая фикс. сумма."""
    from app.models import Achievement

    achievement = db.exec(select(Achievement).where(Achievement.code == code)).first()
    if achievement and achievement.tier:
        return TIER_COINS.get(achievement.tier, 20)
    return LEGACY_ACHIEVEMENT_COINS.get(code, 20)
