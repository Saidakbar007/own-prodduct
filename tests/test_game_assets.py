"""
Тесты заглушек картинок и поиска готовых файлов (.webp -> .png): если
файла нет на диске — отдаём SVG-заглушку по тому же роуту; если есть —
ссылка ведёт на /static/game/..., .webp имеет приоритет над .png (v6c).
"""

import os

from app.services.game_assets import (
    bg_image_url,
    boss_image_url,
    frame_image_url,
    game_asset_url,
    hero_image_url,
    persona_image_url,
    pet_image_url,
)


def test_missing_file_returns_placeholder_url(tmp_path, monkeypatch):
    import app.services.game_assets as game_assets_module

    monkeypatch.setattr(game_assets_module, "STATIC_GAME_DIR", str(tmp_path / "game"))

    assert hero_image_url(3) == "/game-placeholder/hero/hero_3"
    assert persona_image_url("warrior", 2) == "/game-placeholder/persona/warrior_2"
    assert pet_image_url("fox", 1) == "/game-placeholder/pets/fox_1"
    assert boss_image_url("laziness") == "/game-placeholder/bosses/laziness"
    assert frame_image_url("rare", 2) == "/game-placeholder/frames/frame_rare_2"
    assert bg_image_url(5) == "/game-placeholder/bg/bg_5"


def test_existing_png_file_returns_static_url(tmp_path, monkeypatch):
    import app.services.game_assets as game_assets_module

    fake_dir = str(tmp_path / "game")
    monkeypatch.setattr(game_assets_module, "STATIC_GAME_DIR", fake_dir)

    hero_dir = os.path.join(fake_dir, "hero")
    os.makedirs(hero_dir, exist_ok=True)
    with open(os.path.join(hero_dir, "hero_3.png"), "wb") as f:
        f.write(b"fake-png-bytes")

    assert game_asset_url("hero", "hero_3") == "/static/game/hero/hero_3.png"
    assert game_asset_url("hero", "hero_4") == "/game-placeholder/hero/hero_4"


def test_webp_preferred_over_png(tmp_path, monkeypatch):
    import app.services.game_assets as game_assets_module

    fake_dir = str(tmp_path / "game")
    monkeypatch.setattr(game_assets_module, "STATIC_GAME_DIR", fake_dir)

    hero_dir = os.path.join(fake_dir, "hero")
    os.makedirs(hero_dir, exist_ok=True)
    with open(os.path.join(hero_dir, "hero_1.png"), "wb") as f:
        f.write(b"fake-png-bytes")
    with open(os.path.join(hero_dir, "hero_1.webp"), "wb") as f:
        f.write(b"fake-webp-bytes")

    assert game_asset_url("hero", "hero_1") == "/static/game/hero/hero_1.webp"


def test_hero_and_persona_art_exist_on_disk_as_webp():
    """Реальный арт из scripts/process_art.py — 5 стадий героя и 5 стадий каждой из 5 личностей."""
    for stage in range(1, 6):
        assert hero_image_url(stage) == f"/static/game/hero/hero_{stage}.webp"
    for code in ("warrior", "sage", "monk", "healer", "bard"):
        for stage in range(1, 6):
            assert persona_image_url(code, stage) == f"/static/game/persona/{code}_{stage}.webp"


def test_placeholder_route_serves_svg(client):
    resp = client.get("/game-placeholder/hero/hero_3")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/svg+xml")
    assert "<svg" in resp.text
    assert "3" in resp.text


def test_persona_placeholder_route_known_codes(client):
    for code in ("warrior", "sage", "monk", "healer", "bard"):
        resp = client.get(f"/game-placeholder/persona/{code}_1")
        assert resp.status_code == 200
        assert "<svg" in resp.text


def test_frame_placeholder_route_shows_rarity(client):
    resp = client.get("/game-placeholder/frames/frame_epic_1")
    assert resp.status_code == 200
    assert "эпическая" in resp.text


def test_badge_placeholder_route(client):
    resp = client.get("/game-placeholder/badges/first_habit")
    assert resp.status_code == 200
    assert "first_habit" in resp.text
