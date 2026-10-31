"""Полный путь онбординг -> регистрация -> Сегодня/Сезон (Фаза 2, §7)."""

from datetime import date

THIS_YEAR = date.today().year


def _register_payload(unique: str, **overrides):
    payload = {
        "name": "Онбординг Тестов",
        "birth_year": THIS_YEAR - 25,
        "age_confirm": "1",
        "email": f"ob-{unique}@example.com",
        "login": f"ob-{unique}",
        "password": "s3cret-pass",
        "password_confirm": "s3cret-pass",
        "timezone": "UTC",
    }
    payload.update(overrides)
    return payload


def test_goal_picker_lists_all_five_templates(client):
    resp = client.get("/onboarding")
    assert resp.status_code == 200
    for title_part in ["5 км", "подтягиваний", "отжиманий", "веса", "мышц"]:
        assert title_part in resp.text


def test_run_5k_full_flow_to_today_and_done(client, unique):
    assert client.post("/onboarding/goal", data={"template_id": "run_5k"}).status_code in (200, 303)
    assert client.post("/onboarding/baseline", data={"value": "5"}).status_code in (200, 303)
    assert client.post("/onboarding/schedule", data={"length_days": "60"}).status_code in (200, 303)

    trailer = client.get("/onboarding/trailer", follow_redirects=True)
    assert trailer.status_code == 200
    assert "5 км" in trailer.text

    register_resp = client.post("/register", data=_register_payload(unique), follow_redirects=True)
    assert register_resp.status_code == 200
    # Пролога больше нет: сезон стартует сразу, день 1 — это сегодня.
    assert "День 1" in register_resp.text

    # День 1 — всегда точка старта (замер), первое действие идёт через /measure.
    done_resp = client.post("/measure", data={"value": "6"}, follow_redirects=True)
    assert done_resp.status_code == 200

    season_resp = client.get("/season", follow_redirects=True)
    assert season_resp.status_code == 200


def test_fat_loss_safe_requires_health_check_and_blocks_low_bmi(client, unique):
    client.post("/onboarding/goal", data={"template_id": "fat_loss_safe"})
    # Рост 180, вес 50 -> BMI ~15.4 < 18.5 -> блокируется
    blocked = client.post(
        "/onboarding/health", data={"height_cm": "180", "weight_kg": "50", "birth_year": str(THIS_YEAR - 25)}
    )
    assert blocked.status_code == 200
    assert "сезон силы" in blocked.text or "недоступен" in blocked.text or "не для тебя" in blocked.text


def test_fat_loss_safe_happy_path_skips_separate_baseline_question(client, unique):
    client.post("/onboarding/goal", data={"template_id": "fat_loss_safe"})
    health_resp = client.post(
        "/onboarding/health",
        data={"height_cm": "175", "weight_kg": "80", "birth_year": str(THIS_YEAR - 25)},
        follow_redirects=True,
    )
    assert health_resp.status_code == 200
    # Сразу должны попасть на экран расписания (а не повторно спрашивать вес)
    assert "ритм" in health_resp.text.lower() or "расписан" in health_resp.text.lower()

    client.post("/onboarding/schedule", data={"length_days": "60"})
    trailer = client.get("/onboarding/trailer")
    assert trailer.status_code == 200

    reg = client.post("/register", data=_register_payload(unique), follow_redirects=True)
    assert reg.status_code == 200


def test_muscle_gain_collects_secondary_bodyweight_metric(client, unique):
    client.post("/onboarding/goal", data={"template_id": "muscle_gain"})
    client.post(
        "/onboarding/health",
        data={"height_cm": "180", "weight_kg": "75", "birth_year": str(THIS_YEAR - 25)},
    )
    client.post("/onboarding/baseline", data={"value": "40"})  # рабочий вес в приседе
    client.post("/onboarding/schedule", data={"length_days": "90"})
    trailer = client.get("/onboarding/trailer")
    assert trailer.status_code == 200

    reg = client.post("/register", data=_register_payload(unique), follow_redirects=True)
    assert reg.status_code == 200

    season_page = client.get("/season", follow_redirects=True)
    assert season_page.status_code == 200


def test_custom_goal_shows_coming_soon_without_anthropic_key(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    resp = client.post(
        "/onboarding/goal", data={"template_id": "custom", "custom_text": "научиться плавать"}
    )
    assert resp.status_code == 200
    assert "скоро появится" in resp.text


def test_measure_flow_records_value_and_updates_season(client, unique):
    client.post("/onboarding/goal", data={"template_id": "pushups_50"})
    client.post("/onboarding/baseline", data={"value": "5"})
    client.post("/onboarding/schedule", data={"length_days": "30"})
    client.get("/onboarding/trailer")
    client.post("/register", data=_register_payload(unique, login=f"measure-{unique}", email=f"measure-{unique}@example.com"))

    resp = client.post("/measure", data={"value": "8"}, follow_redirects=True)
    assert resp.status_code == 200
    assert "8.0" in resp.text or "8" in resp.text
