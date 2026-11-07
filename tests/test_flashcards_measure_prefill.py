"""/measure предзаполняется числом карточек, усвоенных на 35-дневном
интервале (F5) — для цели flashcards_mastered, по аналогии с таймером
фокуса (sum_logged_minutes_since_last_measure)."""

from datetime import date, timedelta

from sqlmodel import select

from app.models import Season, User
from app.newlife.flashcard_decks import load_decks
from app.services.flashcards import INTERVALS_DAYS, record_review

THIS_YEAR = date.today().year


def _register_payload(unique: str, **overrides):
    payload = {
        "name": "Карточки Замер Тест",
        "birth_year": THIS_YEAR - 25,
        "age_confirm": "1",
        "email": f"fcm-{unique}@example.com",
        "login": f"fcm-{unique}",
        "password": "s3cret-pass",
        "password_confirm": "s3cret-pass",
        "timezone": "UTC",
    }
    payload.update(overrides)
    return payload


def test_measure_prefills_mastered_card_count_for_flashcards_mastered_goal(client, unique, db_session):
    client.post("/onboarding/goal", data={"template_id": "flashcards_mastered"})
    client.post("/onboarding/baseline", data={"value": "0"})
    client.post("/onboarding/schedule", data={"length_days": "30"})
    client.get("/onboarding/trailer")
    reg = client.post("/register", data=_register_payload(unique), follow_redirects=True)
    assert reg.status_code == 200

    user = db_session.exec(select(User).where(User.login == f"fcm-{unique}")).first()
    season = db_session.exec(select(Season).where(Season.uid == user.id)).first()

    deck_id = next(iter(load_decks().keys()))
    deck = load_decks()[deck_id]
    card_id = deck.cards[0].id

    t = season.start_date
    for _ in range(len(INTERVALS_DAYS)):  # поднимаем карточку до последней ступени (35 дней)
        record_review(db_session, user.id, deck_id, card_id, correct=True, today=t)
        t = t + timedelta(days=1)

    resp = client.get("/measure")
    assert resp.status_code == 200
    assert 'value="1.0"' in resp.text
