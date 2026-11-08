"""Фото сфер (доп. задача, см. docs/decisions/DECISIONS.md → «Этап
"Доделай" + guide + wger»): 11 фото, по одному на сферу, из Unsplash
(лицензия/авторство — assets/photos/CREDITS.json), на экране точки А
каждой сферы (onboarding/sphere-level)."""

import json

ALL_SPHERE_IDS = [
    "body", "mind", "character", "social", "career", "finance",
    "relationships", "knowledge", "values", "lifestyle", "energy",
]


def test_all_eleven_sphere_photos_exist_and_served():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    for sphere_id in ALL_SPHERE_IDS:
        resp = client.get(f"/assets/photos/spheres/{sphere_id}.webp")
        assert resp.status_code == 200, f"{sphere_id}: фото не отдаётся"
        assert resp.headers["content-type"] == "image/webp"
        assert len(resp.content) <= 200 * 1024, f"{sphere_id}: больше 200 КБ"


def test_credits_json_has_attribution_for_every_sphere_photo():
    with open("assets/photos/CREDITS.json", encoding="utf-8") as f:
        credits = json.load(f)
    spheres = credits["spheres"]
    for sphere_id in ALL_SPHERE_IDS:
        entry = spheres[sphere_id]
        assert entry["downloaded"] is True
        assert entry["photographer"].strip()
        assert entry["unsplash_url"].startswith("https://unsplash.com/")


def test_sphere_level_screen_shows_the_sphere_photo(client, unique):
    client.post("/onboarding/spheres", data={"sphere_ids": ["energy"]})
    resp = client.get("/onboarding/sphere-level")
    assert resp.status_code == 200
    assert "/assets/photos/spheres/energy.webp" in resp.text
