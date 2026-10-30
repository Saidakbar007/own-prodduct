"""
Вызов «Спорим?» (§7 п.7, Фаза 3): дуэль двух сезонов по одному шаблону.
Соперник видит прогресс и доказательства (кроме фото тела), может нажать
«сомневаюсь» — отметку нужно подтвердить заново, иначе она не засчитывается
в вызове (сам сезон и его честность это не трогает). Без денег и ставок.
"""

import secrets
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Session, select

from app.models import Challenge, ChallengeDispute, SeasonDay

DEFAULT_TERMS = 'Дойти до конца сезона со статусом не ниже «Сезон пройден»'


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_challenge(db: Session, from_uid: int, season_id_from: int, terms_text: str = DEFAULT_TERMS) -> Challenge:
    challenge = Challenge(
        from_uid=from_uid,
        season_id_from=season_id_from,
        invite_code=secrets.token_urlsafe(6),
        terms_text=terms_text,
    )
    db.add(challenge)
    db.commit()
    db.refresh(challenge)
    return challenge


def get_by_invite_code(db: Session, code: str) -> Optional[Challenge]:
    return db.exec(select(Challenge).where(Challenge.invite_code == code)).first()


def accept_challenge(db: Session, challenge: Challenge, to_uid: int, season_id_to: int) -> Challenge:
    challenge.to_uid = to_uid
    challenge.season_id_to = season_id_to
    challenge.status = "active"
    db.add(challenge)
    db.commit()
    db.refresh(challenge)
    return challenge


def decline_challenge(db: Session, challenge: Challenge) -> Challenge:
    challenge.status = "declined"
    db.add(challenge)
    db.commit()
    db.refresh(challenge)
    return challenge


def dispute_day(db: Session, challenge_id: int, day_number: int, uid: int, disputed_by: int) -> ChallengeDispute:
    existing = db.exec(
        select(ChallengeDispute).where(
            ChallengeDispute.challenge_id == challenge_id,
            ChallengeDispute.day_number == day_number,
            ChallengeDispute.uid == uid,
        )
    ).first()
    if existing:
        return existing
    dispute = ChallengeDispute(challenge_id=challenge_id, day_number=day_number, uid=uid, disputed_by=disputed_by)
    db.add(dispute)
    db.commit()
    db.refresh(dispute)
    return dispute


def confirm_dispute(db: Session, dispute: ChallengeDispute) -> ChallengeDispute:
    dispute.status = "confirmed"
    dispute.confirmed_at = _utcnow()
    db.add(dispute)
    db.commit()
    db.refresh(dispute)
    return dispute


def pending_disputed_days(db: Session, challenge_id: int, uid: int) -> set[int]:
    return set(
        db.exec(
            select(ChallengeDispute.day_number).where(
                ChallengeDispute.challenge_id == challenge_id,
                ChallengeDispute.uid == uid,
                ChallengeDispute.status == "pending",
            )
        ).all()
    )


def counted_progress(db: Session, season_id: int, challenge_id: int, uid: int) -> int:
    """Дни, которые засчитываются в вызов: done/minimal/rescued минус
    оспоренные и ещё не подтверждённые повторно."""
    excluded = pending_disputed_days(db, challenge_id, uid)
    days = db.exec(
        select(SeasonDay.day_number).where(
            SeasonDay.season_id == season_id, SeasonDay.status.in_(["done", "minimal", "rescued"])
        )
    ).all()
    return sum(1 for d in days if d not in excluded)


def determine_winner(db: Session, challenge: Challenge) -> Optional[int]:
    if not challenge.season_id_to:
        return None
    from_count = counted_progress(db, challenge.season_id_from, challenge.id, challenge.from_uid)
    to_count = counted_progress(db, challenge.season_id_to, challenge.id, challenge.to_uid)
    if from_count == to_count:
        return None
    return challenge.from_uid if from_count > to_count else challenge.to_uid
