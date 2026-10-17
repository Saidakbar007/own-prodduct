"""
Trust score (0-100): доля отметок с доказательством/подтверждением другом,
минус штраф за подозрительные паттерны. Используется как множитель очков.
Подтверждения друзей взвешены (см. app/services/collusion.py) — ноль для
подтверждающих с низким trust, ×0.25 для подозрительных взаимных пар.
"""

from sqlmodel import Session, select

from app.models import Habit, HabitConfirmation, HabitHistory
from app.services.collusion import confirmation_weight


def compute_trust_score(db: Session, uid: int) -> int:
    """Пересчитывает trust score пользователя с нуля по его истории отметок."""
    habit_ids = [h.id for h in db.exec(select(Habit).where(Habit.uid == uid)).all()]
    if not habit_ids:
        return 100

    entries = db.exec(select(HabitHistory).where(HabitHistory.h_id.in_(habit_ids))).all()
    completions = [e for e in entries if e.kind in ("done", "minimal")]
    if not completions:
        return 100

    confirmations_by_history = {}
    for c in db.exec(select(HabitConfirmation).where(HabitConfirmation.status == "confirmed")).all():
        confirmations_by_history.setdefault(c.history_id, []).append(c)

    verified_weight = 0.0
    for e in completions:
        if e.proof_path:
            verified_weight += 1.0
            continue
        confirmations = confirmations_by_history.get(e.id, [])
        if confirmations:
            # берём лучшее (максимальное) подтверждение, если их несколько
            verified_weight += max(confirmation_weight(db, c, uid) for c in confirmations)

    score = int(verified_weight / len(completions) * 100)

    # штраф: подавляющее большинство отметок — буквально "в последнюю минуту" суток
    late_night = sum(1 for e in completions if e.time.hour == 23 and e.time.minute >= 58)
    if late_night / len(completions) > 0.5:
        score -= 15

    # штраф: отметки "пачками" — 5+ подряд в пределах одной минуты (похоже на массовую подделку задним числом)
    sorted_times = sorted(e.time for e in entries)
    for i in range(len(sorted_times) - 4):
        if (sorted_times[i + 4] - sorted_times[i]).total_seconds() <= 60:
            score -= 20
            break

    return max(0, min(100, score))


def trust_multiplier(trust_score: int) -> float:
    """Множитель очков от trust score: 0 -> 0.5x, 100 -> 1.0x."""
    return 0.5 + 0.5 * (trust_score / 100)


def refresh_trust_score(db: Session, user) -> int:
    """Пересчитывает и сохраняет trust score пользователя."""
    user.trust_score = compute_trust_score(db, user.id)
    db.add(user)
    db.commit()
    return user.trust_score
