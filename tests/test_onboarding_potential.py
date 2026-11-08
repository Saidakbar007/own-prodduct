"""«Потенциал 30/60/90» — новый шаг онбординга между WOOP и трейлером
(NEWLIFE_2_0.md §2.1 п.8, §Этап 3 Онбординг): карточки только для целей,
покрытых `content/potential_30_60_90.yaml` И относящихся к сферам,
выбранным на экране 2 — остальные цели/сферы просто не показываются."""


def _advance_to_woop(client, *, spheres, goal_template_id, baseline_value):
    client.get("/onboarding")
    client.post("/onboarding/spheres", data={"sphere_ids": spheres})
    for _ in spheres:
        client.get("/onboarding/sphere-level")
        client.post("/onboarding/sphere-level", data={"option_index": "1"})

    client.post("/onboarding/goal", data={"template_id": goal_template_id})
    client.post("/onboarding/baseline", data={"value": str(baseline_value)})
    client.post("/onboarding/schedule", data={"length_days": "30"})

    client.post("/onboarding/mode", data={"wake_time": "06:30", "sleep_time": "22:30"})
    client.post("/onboarding/commitments", data={"action": "next", "commute_minutes": "0"})
    client.post("/onboarding/daily-minutes", data={"daily_minutes": "30"})
    client.post("/onboarding/chronotype", data={"chronotype": "morning"})
    client.post("/onboarding/constraints", data={"constraints": []})
    client.post("/onboarding/woop/obstacle", data={"main_obstacle": "forget"})
    client.post("/onboarding/woop", data={"plan": "anchor"})


def test_potential_shows_card_for_selected_sphere_goal(client, unique):
    _advance_to_woop(client, spheres=["body"], goal_template_id="pushups_50", baseline_value=5)

    resp = client.get("/onboarding/potential")
    assert resp.status_code == 200
    assert "отжиманий" in resp.text  # day_30 текст pushups_50
    assert "20 отжиманий подряд" in resp.text  # day_90 текст pushups_50


def test_potential_hides_cards_outside_selected_spheres(client, unique):
    # Сфера "career" не покрыта content/potential_30_60_90.yaml вовсе —
    # экран не блокирует переход дальше, просто не показывает карточек.
    _advance_to_woop(client, spheres=["career"], goal_template_id="pushups_50", baseline_value=5)

    resp = client.get("/onboarding/potential")
    assert resp.status_code == 200
    assert "отжиманий" not in resp.text

    # Переход дальше работает независимо от наличия карточек.
    trailer = client.get("/onboarding/trailer")
    assert trailer.status_code == 200


def test_woop_now_redirects_into_potential_before_trailer(client, unique):
    _advance_to_woop(client, spheres=["energy"], goal_template_id="breathing_practice", baseline_value=1)

    resp = client.post("/onboarding/woop", data={"plan": "anchor"}, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"].endswith("/onboarding/potential")
