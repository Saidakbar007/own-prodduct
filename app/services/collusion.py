"""
Анти-сговор в вызовах "Спорим?" (перенесено из archive/v6 app/services/
collusion.py и переписано под новую модель — там считался вес подтверждений
привычек, здесь считаем долю вызовов на одного и того же соперника).

Подозрительный паттерн — пара, которая снова и снова вызывает только друг
друга и никогда не оспаривает отметки друг друга даже при явно
неправдоподобных замерах. Это не блокирует вызовы — только помечает пару
для честности (снижение trust_score и исключение из публичных составов,
см. app.services.trust.meets_squad_trust_threshold), не блокирует продукт.
"""

from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.models import Challenge

MUTUAL_PAIR_WINDOW_DAYS = 90
MUTUAL_PAIR_THRESHOLD = 0.8
MUTUAL_PAIR_MIN_CHALLENGES = 3


def _opponents_for(db: Session, uid: int, days: int = MUTUAL_PAIR_WINDOW_DAYS) -> list[int]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    challenges = db.exec(
        select(Challenge).where(
            ((Challenge.from_uid == uid) | (Challenge.to_uid == uid)),
            Challenge.created_at >= cutoff,
            Challenge.to_uid.is_not(None),
        )
    ).all()
    opponents = []
    for c in challenges:
        other = c.to_uid if c.from_uid == uid else c.from_uid
        if other is not None:
            opponents.append(other)
    return opponents


def is_suspicious_pair(db: Session, uid_a: int, uid_b: int) -> bool:
    """≥80% вызовов uid_a за последние 90 дней — именно с uid_b, и их не
    меньше MUTUAL_PAIR_MIN_CHALLENGES — похоже на пару, которая вызывает
    только друг друга, а не честно соревнуется с составом волны."""
    opponents = _opponents_for(db, uid_a)
    if len(opponents) < MUTUAL_PAIR_MIN_CHALLENGES:
        return False
    matching = sum(1 for o in opponents if o == uid_b)
    return (matching / len(opponents)) >= MUTUAL_PAIR_THRESHOLD
