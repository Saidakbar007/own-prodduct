"""
Тесты галереи ассетов (v6d): 10 вкладок, счётчик готовности, подписи
стадий, редкость/цена у предметов, доступ только админам.
"""

from sqlmodel import select

from app.models import User
from app.services.gallery import IMAGE_LESS_SLOTS, build_gallery
from tests.conftest import register_user


def test_gallery_has_ten_tabs(session):
    gallery = build_gallery(session)
    codes = {tab["code"] for tab in gallery["tabs"]}
    assert codes == {
        "hero", "personas", "pets", "bosses", "bg", "frames", "titles", "effects", "badges", "season",
    }


def test_hero_tab_has_five_stage_entries(session):
    gallery = build_gallery(session)
    hero_tab = next(t for t in gallery["tabs"] if t["code"] == "hero")
    assert len(hero_tab["entries"]) == 5
    assert "стадия 1/5" in hero_tab["entries"][0]["label"]


def test_persona_tab_has_25_entries_with_level_range_label(session):
    gallery = build_gallery(session)
    tab = next(t for t in gallery["tabs"] if t["code"] == "personas")
    assert len(tab["entries"]) == 25
    labels = [e["label"] for e in tab["entries"]]
    assert any("Воин · стадия 3 · ур. сферы 8" in label for label in labels)


def test_pet_tab_has_15_entries_with_streak_days_label(session):
    gallery = build_gallery(session)
    tab = next(t for t in gallery["tabs"] if t["code"] == "pets")
    assert len(tab["entries"]) == 15
    labels = [e["label"] for e in tab["entries"]]
    assert any("Лис" in label and "30 дней" in label for label in labels)


def test_boss_tab_has_six_entries_without_fake_power_attribute(session):
    gallery = build_gallery(session)
    tab = next(t for t in gallery["tabs"] if t["code"] == "bosses")
    assert len(tab["entries"]) == 6
    for entry in tab["entries"]:
        assert "сила" not in entry["label"].lower()


def test_shop_item_entries_show_rarity_and_price(session):
    gallery = build_gallery(session)
    bg_tab = next(t for t in gallery["tabs"] if t["code"] == "bg")
    assert len(bg_tab["entries"]) >= 12
    labelled = bg_tab["entries"][0]
    assert any(r in labelled["sublabel"] for r in ("Обычный", "Редкий", "Эпический", "Легендарный"))
    assert "выдаётся" in labelled["sublabel"]


def test_titles_and_effects_excluded_from_readiness_count(session):
    gallery = build_gallery(session)
    title_tab = next(t for t in gallery["tabs"] if t["code"] == "titles")
    effect_tab = next(t for t in gallery["tabs"] if t["code"] == "effects")
    for tab in (title_tab, effect_tab):
        for entry in tab["entries"]:
            assert entry.get("needs_art", True) is False


def test_season_tab_not_double_counted_in_readiness(session):
    gallery = build_gallery(session)
    season_tab = next(t for t in gallery["tabs"] if t["code"] == "season")
    assert len(season_tab["entries"]) == 6  # 2 bg + 2 frame + 1 title + 1 effect
    # счётчик не должен превышать разумный максимум без двойного учёта сезонных
    assert gallery["total"] < 150


def test_readiness_counter_matches_real_art_state(session):
    gallery = build_gallery(session)
    # арт героя/личностей реально есть на диске (v6c) -> хотя бы 30 готово
    assert gallery["done"] >= 30
    assert gallery["done"] <= gallery["total"]


def test_badge_entries_show_tier_label(session):
    gallery = build_gallery(session)
    tab = next(t for t in gallery["tabs"] if t["code"] == "badges")
    assert len(tab["entries"]) >= 20
    gold_entries = [e for e in tab["entries"] if "золото" in e["sublabel"]]
    assert len(gold_entries) >= 1


def test_gallery_route_requires_admin(client, session, monkeypatch):
    monkeypatch.setenv("ADMIN_LOGINS", "realadmin")
    register_user(client, login="notadmin", mail="notadmin@example.com")
    resp = client.get("/admin/gallery")
    assert resp.status_code == 404


def test_gallery_route_renders_for_admin(client, session, monkeypatch):
    monkeypatch.setenv("ADMIN_LOGINS", "galleryadmin")
    register_user(client, login="galleryadmin", mail="galleryadmin@example.com")
    resp = client.get("/admin/gallery")
    assert resp.status_code == 200
    assert "Готово" in resp.text
    for label in ("Герой", "Личности", "Питомцы", "Боссы", "Фоны", "Рамки", "Титулы", "Эффекты отметки", "Значки достижений", "Сезонные предметы"):
        assert label in resp.text
