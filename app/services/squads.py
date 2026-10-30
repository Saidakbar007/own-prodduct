"""
«Состав» (§7 п.6, Фаза 3): группы до 8 человек внутри волны по одному
шаблону. Анонимно по умолчанию, реакции-"огоньки" (без личных сообщений),
выход в один клик. Видна только отметка и реакции — не фото (§9).
"""

from datetime import date, datetime, timezone
from typing import Optional

from sqlmodel import Session, select

from app.models import Squad, SquadMember, SquadReaction, User

MAX_SQUAD_SIZE = 8


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def assign_squad(db: Session, wave_id: int, template_id: str, season_id: int, uid: int) -> SquadMember:
    """Находит состав волны с местом (<8 активных) или создаёт новый."""
    squads = db.exec(
        select(Squad).where(Squad.wave_id == wave_id, Squad.template_id == template_id)
    ).all()

    for squad in squads:
        active = db.exec(
            select(SquadMember).where(SquadMember.squad_id == squad.id, SquadMember.left_at.is_(None))
        ).all()
        if len(active) < MAX_SQUAD_SIZE:
            member = SquadMember(squad_id=squad.id, uid=uid, season_id=season_id)
            db.add(member)
            db.commit()
            db.refresh(member)
            return member

    squad = Squad(wave_id=wave_id, template_id=template_id)
    db.add(squad)
    db.commit()
    db.refresh(squad)

    member = SquadMember(squad_id=squad.id, uid=uid, season_id=season_id)
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


def leave_squad(db: Session, uid: int, squad_id: int) -> bool:
    member = db.exec(
        select(SquadMember).where(
            SquadMember.squad_id == squad_id, SquadMember.uid == uid, SquadMember.left_at.is_(None)
        )
    ).first()
    if not member:
        return False
    member.left_at = _utcnow()
    db.add(member)
    db.commit()
    return True


def set_anonymous(db: Session, uid: int, squad_id: int, anonymous: bool) -> bool:
    member = db.exec(
        select(SquadMember).where(
            SquadMember.squad_id == squad_id, SquadMember.uid == uid, SquadMember.left_at.is_(None)
        )
    ).first()
    if not member:
        return False
    member.anonymous = anonymous
    db.add(member)
    db.commit()
    return True


def display_name(user: User, member: SquadMember) -> str:
    """Анонимно по умолчанию — ник вместо имени/логина."""
    if member.anonymous:
        return f"Участник #{user.id:03d}"
    return user.name or user.login


def active_members(db: Session, squad_id: int) -> list[SquadMember]:
    return db.exec(
        select(SquadMember).where(SquadMember.squad_id == squad_id, SquadMember.left_at.is_(None))
    ).all()


def add_reaction(db: Session, squad_id: int, from_uid: int, to_uid: int, on_date: date, emoji: str = "🔥") -> bool:
    """Одна реакция от человека на день другого человека — повторная игнорируется."""
    existing = db.exec(
        select(SquadReaction).where(
            SquadReaction.squad_id == squad_id,
            SquadReaction.from_uid == from_uid,
            SquadReaction.to_uid == to_uid,
            SquadReaction.reacted_on == on_date,
        )
    ).first()
    if existing:
        return False
    db.add(
        SquadReaction(squad_id=squad_id, from_uid=from_uid, to_uid=to_uid, reacted_on=on_date, emoji=emoji)
    )
    db.commit()
    return True


def reaction_count(db: Session, squad_id: int, to_uid: int, on_date: date) -> int:
    return len(
        db.exec(
            select(SquadReaction.id).where(
                SquadReaction.squad_id == squad_id,
                SquadReaction.to_uid == to_uid,
                SquadReaction.reacted_on == on_date,
            )
        ).all()
    )


def my_squad_membership(db: Session, uid: int, season_id: int) -> Optional[SquadMember]:
    return db.exec(
        select(SquadMember).where(
            SquadMember.uid == uid, SquadMember.season_id == season_id, SquadMember.left_at.is_(None)
        )
    ).first()
