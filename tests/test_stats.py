"""Тесты страницы статистики: уровень создаётся при регистрации, повышается по очкам."""

from sqlmodel import select

from app.models import Level, User
from app.services.levels import level_for_xp, rank_for_level
from app.services.points import award_points
from tests.conftest import register_user


def test_stats_page_shows_starting_level(client):
    register_user(client, login="sara", mail="sara@example.com")
    resp = client.get("/stats")
    assert resp.status_code == 200
    assert "Новичок" in resp.text
    assert "Ур. 1" in resp.text
    assert "0" in resp.text  # 0 XP всего


def test_level_upgrades_after_enough_points(client, session):
    register_user(client, login="tom", mail="tom@example.com")
    user = session.exec(select(User).where(User.login == "tom")).first()

    award_points(session, user, 150)

    level = session.exec(select(Level).where(Level.uid == user.id)).first()
    assert level.point == 150
    expected_level = level_for_xp(150)
    assert expected_level == 2  # 100 XP -> ур.2, 150 ещё не хватает на ур.3 (220)
    assert level.name == rank_for_level(expected_level) == "Новичок"

    resp = client.get("/stats")
    assert f"Ур. {expected_level}" in resp.text


def test_rank_changes_once_level_crosses_into_next_rank(client, session):
    register_user(client, login="uma2", mail="uma2@example.com")
    user = session.exec(select(User).where(User.login == "uma2")).first()

    # Уровень 6 (начало ранга "Ученик") достигается на 700 суммарного XP
    award_points(session, user, 700)

    level = session.exec(select(Level).where(Level.uid == user.id)).first()
    assert level_for_xp(level.point) == 6
    assert level.name == "Ученик"

    resp = client.get("/stats")
    assert "Ученик" in resp.text
