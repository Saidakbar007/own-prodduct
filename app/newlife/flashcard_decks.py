"""
Каталог наборов карточек (PRD 1.0 F5) — `content/flashcard_decks.yaml`,
схема и загрузчик с кэшем. Сам движок интервальных повторений (расчёт
due-дат, лимит новых карточек/день) — app/services/flashcards.py.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

_PATH = Path(__file__).resolve().parent.parent.parent / "content" / "flashcard_decks.yaml"


class DeckText(BaseModel):
    ru: str
    uz: str

    def text(self, lang: str) -> str:
        return self.uz if lang == "uz" else self.ru


class Flashcard(BaseModel):
    """Лицевая сторона (`front`) — либо одно слово (английские карточки,
    само слово изучения важнее перевода заголовка), либо вопрос на ru/uz
    (карточки «Знания») — оба варианта, без двух разных схем."""
    id: str
    front: str | DeckText
    back: DeckText

    def front_text(self, lang: str) -> str:
        if isinstance(self.front, str):
            return self.front
        return self.front.text(lang)


class FlashcardDeck(BaseModel):
    title: DeckText
    cards: list[Flashcard] = Field(min_length=1)


@lru_cache(maxsize=1)
def load_decks() -> dict[str, FlashcardDeck]:
    data = yaml.safe_load(_PATH.read_text(encoding="utf-8")) or {}
    decks = {deck_id: FlashcardDeck.model_validate(deck) for deck_id, deck in data.items()}
    all_ids = [card.id for deck in decks.values() for card in deck.cards]
    if len(all_ids) != len(set(all_ids)):
        raise ValueError("content/flashcard_decks.yaml: повторяющийся id карточки")
    return decks


def deck_meta(deck_id: str) -> FlashcardDeck | None:
    return load_decks().get(deck_id)


def card_meta(deck_id: str, card_id: str) -> Flashcard | None:
    deck = deck_meta(deck_id)
    if not deck:
        return None
    for card in deck.cards:
        if card.id == card_id:
            return card
    return None
