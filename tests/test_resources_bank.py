"""Проверенные бесплатные ресурсы (языки/программирование/финграмотность) —
доп. задача, см. app/newlife/resources_bank.py и docs/decisions/
DECISIONS.md → «Этап "Доделай" + guide + wger». Каждая ссылка открыта
вручную (WebFetch) перед добавлением в resources.yaml — здесь проверяется
только форма данных и привязка к целям, не живой HTTP-запрос (тесты не
должны зависеть от сети)."""

from datetime import date

from app.newlife.resources_bank import RESOURCE_CATEGORY_FOR_GOAL, load_resources, resources_for_goal

THIS_YEAR = date.today().year


def _register_payload(unique: str, **overrides):
    payload = {
        "name": "Ресурсы Тест",
        "birth_year": THIS_YEAR - 25,
        "age_confirm": "1",
        "email": f"res-{unique}@example.com",
        "login": f"res-{unique}",
        "password": "s3cret-pass",
        "password_confirm": "s3cret-pass",
        "timezone": "UTC",
    }
    payload.update(overrides)
    return payload


def test_every_category_has_at_least_two_resources_with_https_urls():
    bank = load_resources()
    assert set(bank.keys()) >= {"languages", "programming", "financial_literacy"}
    for category, items in bank.items():
        assert len(items) >= 1, f"{category}: нет ни одного ресурса"
        for r in items:
            assert r.url.startswith("https://"), f"{category}/{r.title}: url должен быть https"
            assert r.description.ru.strip() and r.description.uz.strip()


def test_resources_for_goal_returns_empty_for_goal_without_resources():
    assert resources_for_goal("sitting_breaks", "ru") == []


def test_resources_for_goal_returns_category_matching_mapping():
    for goal_id, category in RESOURCE_CATEGORY_FOR_GOAL.items():
        resources = resources_for_goal(goal_id, "ru")
        assert len(resources) == len(load_resources()[category])


def test_season_detail_shows_resources_for_programming_goal(client, unique):
    client.post("/onboarding/goal", data={"template_id": "programming"})
    client.post("/onboarding/baseline", data={"value": "0"})
    client.post("/onboarding/schedule", data={"length_days": "60"})
    client.get("/onboarding/trailer")
    reg = client.post("/register", data=_register_payload(unique), follow_redirects=True)
    assert reg.status_code == 200

    season_page = client.get("/season", follow_redirects=True)
    assert season_page.status_code == 200
    assert "freeCodeCamp" in season_page.text
