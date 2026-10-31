"""
События метрик (§13 ТЗ): воронка онбординга, удержание D1/D7/D30 по
когортам, доля дошедших до Reveal, доля начавших следующий сезон,
вирусность (принятые вызовы на пользователя).
"""

import json
from datetime import datetime
from typing import Optional

from sqlmodel import Session

from app.models import Event

EVENT_TYPES = (
    "onboarding_started",
    "trailer_shown",
    "signup",
    "season_started",
    "day_done",
    "day_minimal",
    "day_missed",
    "second_chance_used",
    "measurement_logged",
    "episode_viewed",
    "card_shared",
    "squad_reaction",
    "challenge_sent",
    "challenge_accepted",
    "reveal_viewed",
    "reveal_shared",
    "next_season_started",
)


def log_event(
    db: Session,
    event_type: str,
    uid: Optional[int] = None,
    season_id: Optional[int] = None,
    meta: Optional[dict] = None,
    created_at: Optional[datetime] = None,
) -> Event:
    """Пишет событие. Не бросает исключение наружу при сбое — метрики не
    должны ронять основной сценарий пользователя."""
    event = Event(
        event_type=event_type,
        uid=uid,
        season_id=season_id,
        meta_json=json.dumps(meta, ensure_ascii=False) if meta else None,
        **({"created_at": created_at} if created_at else {}),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def log_event_safe(db: Session, event_type: str, **kwargs) -> None:
    try:
        log_event(db, event_type, **kwargs)
    except Exception:
        db.rollback()
