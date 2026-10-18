"""
Тесты 3D-арта героя и личностей (v6c): файлы на диске, выбор .webp,
CSS-классы по состоянию личности и ведущей личности на /hero.
"""

import os

from PIL import Image
from sqlmodel import select

from app.models import PointsLog, User
from app.routers.habits import _now
from app.services.game_assets import STATIC_GAME_DIR, hero_image_url, persona_image_url
from tests.conftest import register_user

PERSONA_IMAGE_CODES = ("warrior", "sage", "monk", "healer", "bard")


def test_all_hero_stage_files_exist_on_disk():
    for stage in range(1, 6):
        path = os.path.join(STATIC_GAME_DIR, "hero", f"hero_{stage}.webp")
        assert os.path.isfile(path), path


def test_all_persona_stage_files_exist_on_disk():
    for code in PERSONA_IMAGE_CODES:
        for stage in range(1, 6):
            path = os.path.join(STATIC_GAME_DIR, "persona", f"{code}_{stage}.webp")
            assert os.path.isfile(path), path


def test_hero_and_persona_files_are_valid_webp_rgba():
    path = os.path.join(STATIC_GAME_DIR, "hero", "hero_1.webp")
    im = Image.open(path)
    assert im.format == "WEBP"
    assert im.mode in ("RGBA", "RGB")


def test_canvas_size_consistent_across_all_art_files():
    sizes = set()
    for stage in range(1, 6):
        im = Image.open(os.path.join(STATIC_GAME_DIR, "hero", f"hero_{stage}.webp"))
        sizes.add(im.size)
    for code in PERSONA_IMAGE_CODES:
        for stage in range(1, 6):
            im = Image.open(os.path.join(STATIC_GAME_DIR, "persona", f"{code}_{stage}.webp"))
            sizes.add(im.size)
    assert len(sizes) == 1  # один и тот же холст у всех картинок


def test_each_file_is_reasonably_small():
    """Вес каждой картинки — в пределах разумного для бюджета страницы ~1.5 МБ."""
    for stage in range(1, 6):
        path = os.path.join(STATIC_GAME_DIR, "hero", f"hero_{stage}.webp")
        assert os.path.getsize(path) < 150_000, path
    for code in PERSONA_IMAGE_CODES:
        for stage in range(1, 6):
            path = os.path.join(STATIC_GAME_DIR, "persona", f"{code}_{stage}.webp")
            assert os.path.getsize(path) < 150_000, path


def test_persona_stage_images_grow_in_glow_towards_stage_5():
    """Поздние стадии (больше деталей/свечения) обычно весят больше ранних."""
    for code in PERSONA_IMAGE_CODES:
        size_1 = os.path.getsize(os.path.join(STATIC_GAME_DIR, "persona", f"{code}_1.webp"))
        size_5 = os.path.getsize(os.path.join(STATIC_GAME_DIR, "persona", f"{code}_5.webp"))
        assert size_5 > size_1  # стадия 5 заметно наряднее стадии 1


def test_url_helpers_point_to_webp_files():
    assert hero_image_url(3) == "/static/game/hero/hero_3.webp"
    assert persona_image_url("warrior", 2) == "/static/game/persona/warrior_2.webp"


def test_hero_page_uses_lazy_loading_for_art(client, session):
    register_user(client, login="art1", mail="art1@example.com")
    resp = client.get("/hero")
    assert resp.status_code == 200
    # у героя, питомца и каждой из 5 личностей должен быть loading="lazy"
    assert resp.text.count('loading="lazy"') >= 6


def test_homepage_shows_hero_image_lazily(client, session):
    register_user(client, login="art2", mail="art2@example.com")
    resp = client.get("/")
    assert resp.status_code == 200
    assert 'loading="lazy"' in resp.text
    assert "/static/game/hero/hero_1.webp" in resp.text


def test_asleep_persona_gets_grayscale_css_class(client, session):
    register_user(client, login="art3", mail="art3@example.com")
    resp = client.get("/hero")
    assert resp.status_code == 200
    # свежий пользователь: все личности ещё не активировались -> "спит"
    assert "persona-img-asleep" in resp.text


def test_active_persona_does_not_get_sleep_or_dormant_class(client, session):
    register_user(client, login="art4", mail="art4@example.com")
    user = session.exec(select(User).where(User.login == "art4")).first()
    session.add(PointsLog(uid=user.id, points=10, sphere="strength", time=_now()))
    session.commit()

    resp = client.get("/hero")
    assert resp.status_code == 200
    section = resp.text.split('data-persona="strength"')[1].split('data-persona=')[0]
    assert "persona-img-asleep" not in section
    assert "persona-img-dormant" not in section


def test_leading_persona_card_gets_glow_class(client, session):
    register_user(client, login="art5", mail="art5@example.com")
    user = session.exec(select(User).where(User.login == "art5")).first()
    session.add(PointsLog(uid=user.id, points=50, sphere="intellect", time=_now()))
    session.commit()

    resp = client.get("/hero")
    assert resp.status_code == 200
    marker = resp.text.index('data-persona="intellect"')
    tag_start = resp.text.rindex("<div", 0, marker)  # начало того же <div ...> тега
    opening_tag = resp.text[tag_start:marker]
    assert "persona-card-leading" in opening_tag
