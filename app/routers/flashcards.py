"""
Карточки с интервальным повторением (PRD 1.0 F5) — выбор набора,
сессия повторения (следующая карточка — due/новая, лимит 15 новых/день),
отметка «Вспомнил»/«Не вспомнил». Движок — app/services/flashcards.py.
"""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session

from app.auth import require_user
from app.database import get_session
from app.models import User
from app.newlife.flashcard_decks import load_decks
from app.rendering import render
from app.services.flashcards import debt_count, next_card, record_review
from app.services.usertime import today_for

router = APIRouter()


@router.get("/flashcards")
def flashcards_hub(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    today = today_for(user)
    decks = [
        {
            "id": deck_id,
            "title": deck.title.text(user.language),
            "debt": debt_count(db, user.id, deck_id, today),
        }
        for deck_id, deck in load_decks().items()
    ]
    return render(request, "flashcards_hub.html", {"decks": decks, "lang": user.language})


@router.get("/flashcards/{deck_id}")
def flashcards_session(
    deck_id: str, request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)
):
    today = today_for(user)
    deck = load_decks().get(deck_id)
    if not deck:
        return RedirectResponse("/flashcards", status_code=303)

    card = next_card(db, user.id, deck_id, today)
    return render(
        request,
        "flashcards_session.html",
        {
            "deck_id": deck_id,
            "deck_title": deck.title.text(user.language),
            "card": card,
            "front_text": card.front_text(user.language) if card else None,
            "back_text": card.back.text(user.language) if card else None,
            "debt": debt_count(db, user.id, deck_id, today),
            "lang": user.language,
        },
    )


@router.post("/flashcards/{deck_id}/review")
def flashcards_review(
    deck_id: str,
    request: Request,
    card_id: str = Form(...),
    correct: str = Form(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    record_review(db, user.id, deck_id, card_id, correct == "true", today_for(user))
    return RedirectResponse(f"/flashcards/{deck_id}", status_code=303)
