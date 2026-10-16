"""Тесты страницы статистики: уровень создаётся при регистрации, повышается по очкам."""

from sqlmodel import select

from app.models import Level, User
from app.services.points import award_points
from tests.conftest import register_user


def test_stats_page_shows_starting_level(client):
    register_user(client, login="sara", mail="sara@example.com")
    resp = client.get("/stats")
    assert resp.status_code == 200
    assert "Новичок" in resp.text
    assert "0 очков" in resp.text


def test_level_upgrades_after_enough_points(client, session):
    register_user(client, login="tom", mail="tom@example.com")
    user = session.exec(select(User).where(User.login == "tom")).first()

    award_points(session, user, 150)

    resp = client.get("/stats")
    assert "Ученик" in resp.text

    level = session.exec(select(Level).where(Level.uid == user.id)).first()
    assert level.point == 150
    assert level.name == "Ученик"
