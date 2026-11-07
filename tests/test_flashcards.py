"""Движок карточек с интервальным повторением (PRD 1.0 F5) —
app/services/flashcards.py. Схема испытывается на подставном наборе
(не настоящем content/flashcard_decks.yaml) — алгоритм интервалов не
должен зависеть от размера реального контента."""

from datetime import date, timedelta

import app.newlife.flashcard_decks as flashcard_decks
from app.newlife.flashcard_decks import Flashcard, FlashcardDeck, DeckText
from app.models import User
from app.services.flashcards import (
    INTERVALS_DAYS,
    NEW_CARDS_PER_DAY_LIMIT,
    debt_count,
    mastered_count_since,
    next_card,
    record_review,
)

THIS_YEAR = date.today().year
TODAY = date(2026, 11, 7)


def _fake_deck(n_cards: int) -> FlashcardDeck:
    cards = [
        Flashcard(id=f"c{i}", front=f"word{i}", back=DeckText(ru=f"перевод{i}", uz=f"tarjima{i}"))
        for i in range(n_cards)
    ]
    return FlashcardDeck(title=DeckText(ru="Тест", uz="Test"), cards=cards)


def _patch_deck(monkeypatch, n_cards: int = 20):
    deck = _fake_deck(n_cards)
    monkeypatch.setattr(flashcard_decks, "load_decks", lambda: {"test_deck": deck})
    monkeypatch.setattr(flashcard_decks, "deck_meta", lambda deck_id: deck if deck_id == "test_deck" else None)
    return deck


def _make_user(db_session, suffix: str) -> User:
    user = User(
        name="FC", login=f"fc-{suffix}", email=f"fc-{suffix}@example.com",
        password_hash="x", timezone="UTC", birth_year=THIS_YEAR - 25,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_new_card_recalled_correctly_schedules_first_interval(db_session, monkeypatch):
    _patch_deck(monkeypatch)
    user = _make_user(db_session, "a")

    card = next_card(db_session, user.id, "test_deck", TODAY)
    assert card is not None
    review = record_review(db_session, user.id, "test_deck", card.id, correct=True, today=TODAY)

    assert review.stage == 0
    assert review.due_date == TODAY + timedelta(days=INTERVALS_DAYS[0])


def test_correct_review_advances_stage_and_interval(db_session, monkeypatch):
    _patch_deck(monkeypatch)
    user = _make_user(db_session, "b")

    card = next_card(db_session, user.id, "test_deck", TODAY)
    record_review(db_session, user.id, "test_deck", card.id, correct=True, today=TODAY)

    due_day = TODAY + timedelta(days=INTERVALS_DAYS[0])
    review = record_review(db_session, user.id, "test_deck", card.id, correct=True, today=due_day)

    assert review.stage == 1
    assert review.due_date == due_day + timedelta(days=INTERVALS_DAYS[1])


def test_incorrect_review_resets_stage_to_zero_regardless_of_progress(db_session, monkeypatch):
    _patch_deck(monkeypatch)
    user = _make_user(db_session, "c")

    card = next_card(db_session, user.id, "test_deck", TODAY)
    # Продвигаем карточку на несколько ступеней вперёд.
    t = TODAY
    for _ in range(3):
        record_review(db_session, user.id, "test_deck", card.id, correct=True, today=t)
        t = t + timedelta(days=30)  # дата не важна для теста сброса

    review = record_review(db_session, user.id, "test_deck", card.id, correct=False, today=t)
    assert review.stage == 0
    assert review.due_date == t + timedelta(days=INTERVALS_DAYS[0])


def test_due_cards_are_served_before_new_cards(db_session, monkeypatch):
    _patch_deck(monkeypatch, n_cards=5)
    user = _make_user(db_session, "d")

    first = next_card(db_session, user.id, "test_deck", TODAY)
    record_review(db_session, user.id, "test_deck", first.id, correct=False, today=TODAY)  # due again tomorrow

    tomorrow = TODAY + timedelta(days=1)
    next_up = next_card(db_session, user.id, "test_deck", tomorrow)
    assert next_up.id == first.id  # просроченная карточка важнее новой


def test_new_cards_capped_at_daily_limit(db_session, monkeypatch):
    _patch_deck(monkeypatch, n_cards=NEW_CARDS_PER_DAY_LIMIT + 5)
    user = _make_user(db_session, "e")

    for _ in range(NEW_CARDS_PER_DAY_LIMIT):
        card = next_card(db_session, user.id, "test_deck", TODAY)
        assert card is not None
        record_review(db_session, user.id, "test_deck", card.id, correct=True, today=TODAY)

    assert next_card(db_session, user.id, "test_deck", TODAY) is None


def test_debt_count_counts_only_overdue_cards(db_session, monkeypatch):
    _patch_deck(monkeypatch, n_cards=3)
    user = _make_user(db_session, "f")

    card = next_card(db_session, user.id, "test_deck", TODAY)
    record_review(db_session, user.id, "test_deck", card.id, correct=True, today=TODAY)  # due TODAY+1

    assert debt_count(db_session, user.id, "test_deck", TODAY) == 0
    assert debt_count(db_session, user.id, "test_deck", TODAY + timedelta(days=2)) == 1


def test_mastered_count_only_counts_cards_at_the_longest_interval(db_session, monkeypatch):
    _patch_deck(monkeypatch, n_cards=2)
    user = _make_user(db_session, "g")

    card = next_card(db_session, user.id, "test_deck", TODAY)
    t = TODAY
    # Первый вызов создаёт запись (stage 0); нужно ещё len(INTERVALS_DAYS)-1
    # верных повторений, чтобы дойти до последней ступени (35 дней).
    for _ in range(len(INTERVALS_DAYS)):
        record_review(db_session, user.id, "test_deck", card.id, correct=True, today=t)
        t = t + timedelta(days=1)

    assert mastered_count_since(db_session, user.id, "test_deck", TODAY) == 1
