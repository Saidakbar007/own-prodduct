"""
Движок карточек с интервальным повторением (PRD 1.0 F5): интервалы
1→3→7→16→35 дней, лимит 15 новых карточек в день, «не вспомнил» —
интервал сбрасывается на самый короткий (stage 0), а не просто уменьшается.
Наборы карточек — app/newlife/flashcard_decks.py.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlmodel import Session, select

from app.models import FlashcardReview
from app.newlife.flashcard_decks import Flashcard, deck_meta

INTERVALS_DAYS = [1, 3, 7, 16, 35]
NEW_CARDS_PER_DAY_LIMIT = 15


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _review(db: Session, uid: int, deck_id: str, card_id: str) -> Optional[FlashcardReview]:
    return db.exec(
        select(FlashcardReview).where(
            FlashcardReview.uid == uid,
            FlashcardReview.deck_id == deck_id,
            FlashcardReview.card_id == card_id,
        )
    ).first()


def due_card_ids(db: Session, uid: int, deck_id: str, today: date) -> list[str]:
    rows = db.exec(
        select(FlashcardReview.card_id).where(
            FlashcardReview.uid == uid,
            FlashcardReview.deck_id == deck_id,
            FlashcardReview.due_date <= today,
        )
    ).all()
    return list(rows)


def debt_count(db: Session, uid: int, deck_id: str, today: date) -> int:
    """Карточки, которые должны были быть повторены раньше (просрочены) —
    "долг повторений" из PRD F5."""
    rows = db.exec(
        select(FlashcardReview.id).where(
            FlashcardReview.uid == uid,
            FlashcardReview.deck_id == deck_id,
            FlashcardReview.due_date < today,
        )
    ).all()
    return len(rows)


def _new_cards_introduced_today(db: Session, uid: int, deck_id: str, today: date) -> int:
    rows = db.exec(
        select(FlashcardReview.id).where(
            FlashcardReview.uid == uid,
            FlashcardReview.deck_id == deck_id,
            FlashcardReview.introduced_on == today,
        )
    ).all()
    return len(rows)


def next_card(db: Session, uid: int, deck_id: str, today: date) -> Optional[Flashcard]:
    """Следующая карточка сессии: сначала все просроченные/сегодняшние
    повторения, потом новая (если лимит на сегодня не выбран)."""
    deck = deck_meta(deck_id)
    if not deck:
        return None

    due_ids = due_card_ids(db, uid, deck_id, today)
    if due_ids:
        due_id = sorted(due_ids)[0]
        for card in deck.cards:
            if card.id == due_id:
                return card

    if _new_cards_introduced_today(db, uid, deck_id, today) >= NEW_CARDS_PER_DAY_LIMIT:
        return None

    seen_ids = {
        row
        for row in db.exec(
            select(FlashcardReview.card_id).where(FlashcardReview.uid == uid, FlashcardReview.deck_id == deck_id)
        ).all()
    }
    for card in deck.cards:
        if card.id not in seen_ids:
            return card
    return None


def record_review(db: Session, uid: int, deck_id: str, card_id: str, correct: bool, today: date) -> FlashcardReview:
    review = _review(db, uid, deck_id, card_id)
    if review is None:
        review = FlashcardReview(
            uid=uid,
            deck_id=deck_id,
            card_id=card_id,
            stage=0,
            due_date=today + timedelta(days=INTERVALS_DAYS[0]),
            introduced_on=today,
        )
    elif correct:
        review.stage = min(review.stage + 1, len(INTERVALS_DAYS) - 1)
        review.due_date = today + timedelta(days=INTERVALS_DAYS[review.stage])
    else:
        review.stage = 0
        review.due_date = today + timedelta(days=INTERVALS_DAYS[0])
    review.last_reviewed_at = _utcnow()
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


def mastered_count_since(db: Session, uid: int, deck_id: str, since: date) -> int:
    """Карточки, которые верно вспомнились на самом длинном интервале (35
    дней, ≥21 — порог "усвоено надолго" из guide цели flashcards_mastered)
    и были повторены не раньше `since` — для подсказки на /measure."""
    max_stage = len(INTERVALS_DAYS) - 1
    rows = db.exec(
        select(FlashcardReview.id).where(
            FlashcardReview.uid == uid,
            FlashcardReview.deck_id == deck_id,
            FlashcardReview.stage == max_stage,
            FlashcardReview.last_reviewed_at >= datetime.combine(since, datetime.min.time(), tzinfo=timezone.utc),
        )
    ).all()
    return len(rows)
