"""/flashcards (хаб + сессия) против настоящего content/flashcard_decks.yaml
(english_b1 + knowledge_trivia) — доп. задача F5, см. docs/decisions/
DECISIONS.md. Алгоритм интервалов проверен отдельно в tests/test_flashcards.py
на подставном наборе — здесь только маршруты и реальный контент."""

from datetime import date

from app.newlife.flashcard_decks import load_decks

THIS_YEAR = date.today().year


def _register_payload(unique: str, **overrides):
    payload = {
        "name": "Карточки Тест",
        "birth_year": THIS_YEAR - 25,
        "age_confirm": "1",
        "email": f"fcr-{unique}@example.com",
        "login": f"fcr-{unique}",
        "password": "s3cret-pass",
        "password_confirm": "s3cret-pass",
        "timezone": "UTC",
    }
    payload.update(overrides)
    return payload


def _register(client, unique):
    client.post("/onboarding/spheres", data={"sphere_ids": ["body"]})
    client.post("/onboarding/sphere-level", data={"option_index": "2"})
    return client.post("/register", data=_register_payload(unique), follow_redirects=True)


def test_real_decks_have_english_b1_and_knowledge_trivia_with_enough_cards():
    decks = load_decks()
    assert "english_b1" in decks
    assert "knowledge_trivia" in decks
    assert len(decks["english_b1"].cards) >= 100
    assert len(decks["knowledge_trivia"].cards) >= 30


def test_flashcards_hub_lists_both_decks(client, unique):
    _register(client, unique)
    resp = client.get("/flashcards")
    assert resp.status_code == 200
    decks = load_decks()
    for deck in decks.values():
        assert deck.title.ru in resp.text


def test_flashcards_session_shows_a_card_from_the_real_deck(client, unique):
    _register(client, unique)
    resp = client.get("/flashcards/english_b1")
    assert resp.status_code == 200
    assert "cta_reveal" not in resp.text  # ключ должен быть переведён, не показан сырым
    assert "flashcard-reveal" in resp.text


def test_flashcards_session_unknown_deck_redirects_to_hub(client, unique):
    _register(client, unique)
    resp = client.get("/flashcards/does-not-exist", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/flashcards"


def test_reviewing_a_card_advances_the_session(client, unique):
    _register(client, unique)
    first = client.get("/flashcards/knowledge_trivia")
    assert first.status_code == 200

    import re

    match = re.search(r'name="card_id" value="([^"]+)"', first.text)
    assert match, "не нашли card_id на странице сессии"
    card_id = match.group(1)

    resp = client.post(
        "/flashcards/knowledge_trivia/review",
        data={"card_id": card_id, "correct": "true"},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    second = client.get("/flashcards/knowledge_trivia")
    second_match = re.search(r'name="card_id" value="([^"]+)"', second.text)
    assert second_match and second_match.group(1) != card_id
