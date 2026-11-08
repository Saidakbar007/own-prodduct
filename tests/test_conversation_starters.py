"""Банк вопросов для начала разговора (упомянут в guide цели
start_conversations) — доп. задача, см. docs/decisions/DECISIONS.md →
«Этап "Доделай" + guide + wger»."""

from datetime import date

from app.newlife.conversation_starters_bank import load_conversation_starters

THIS_YEAR = date.today().year


def _register_payload(unique: str, **overrides):
    payload = {
        "name": "Разговор Тест",
        "birth_year": THIS_YEAR - 25,
        "age_confirm": "1",
        "email": f"cs-{unique}@example.com",
        "login": f"cs-{unique}",
        "password": "s3cret-pass",
        "password_confirm": "s3cret-pass",
        "timezone": "UTC",
    }
    payload.update(overrides)
    return payload


def test_bank_has_at_least_thirty_bilingual_questions():
    questions = load_conversation_starters()
    assert len(questions) >= 30
    for q in questions:
        assert q.ru.strip() and q.uz.strip()


def test_season_detail_shows_bank_for_start_conversations_goal(client, unique):
    client.post("/onboarding/goal", data={"template_id": "start_conversations"})
    client.post("/onboarding/baseline", data={"value": "1"})
    client.post("/onboarding/schedule", data={"length_days": "30"})
    client.get("/onboarding/trailer")
    reg = client.post("/register", data=_register_payload(unique), follow_redirects=True)
    assert reg.status_code == 200

    season_page = client.get("/season", follow_redirects=True)
    assert season_page.status_code == 200
    assert "Банк вопросов для начала разговора" in season_page.text


def test_season_detail_hides_bank_for_other_goals(client, unique):
    client.post("/onboarding/goal", data={"template_id": "sitting_breaks"})
    client.post("/onboarding/baseline", data={"value": "2"})
    client.post("/onboarding/schedule", data={"length_days": "30"})
    client.get("/onboarding/trailer")
    reg = client.post("/register", data=_register_payload(unique, login=f"cs2-{unique}", email=f"cs2-{unique}@example.com"), follow_redirects=True)
    assert reg.status_code == 200

    season_page = client.get("/season", follow_redirects=True)
    assert season_page.status_code == 200
    assert "Банк вопросов для начала разговора" not in season_page.text
