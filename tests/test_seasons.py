"""
Тесты сезона (v6b): 4 недели, бесплатный трек 30 ступеней, сезонные
предметы каждую 5-ю ступень, выдача без повторов.
"""

from datetime import timedelta

from sqlmodel import select

from app.models import PointsLog, SeasonClaim, ShopItem, User
from app.routers.habits import _now
from app.services.seasons import (
    ITEM_STEP_INTERVAL,
    MAX_STEPS,
    SEASON_ITEMS,
    XP_PER_STEP,
    claim_new_steps,
    claimed_max_step,
    ensure_season_seeded,
    get_active_season,
    reward_for_step,
    season_step,
    season_xp_for_user,
)
from app.services.shop import is_owned
from tests.conftest import register_user


def test_season_seeded_with_items(session):
    season = ensure_season_seeded(session)
    assert season.code == "season1"

    items = session.exec(select(ShopItem).where(ShopItem.season_code == "season1")).all()
    assert len(items) == len(SEASON_ITEMS) == 6


def test_get_active_season_returns_current(session):
    ensure_season_seeded(session)
    season = get_active_season(session)
    assert season is not None
    assert season.code == "season1"


def test_season_step_formula():
    assert season_step(0) == 0
    assert season_step(XP_PER_STEP - 1) == 0
    assert season_step(XP_PER_STEP) == 1
    assert season_step(XP_PER_STEP * 30) == MAX_STEPS
    assert season_step(XP_PER_STEP * 1000) == MAX_STEPS  # не больше максимума


def test_reward_for_step_gives_item_every_5th_step():
    assert reward_for_step(1)["type"] == "coins"
    assert reward_for_step(4)["type"] == "coins"
    assert reward_for_step(5)["type"] == "item"
    assert reward_for_step(10)["type"] == "item"
    assert reward_for_step(5)["code"] == SEASON_ITEMS[0][0]
    assert reward_for_step(10)["code"] == SEASON_ITEMS[1][0]


def test_season_xp_for_user_sums_points_log(client, session):
    register_user(client, login="season1", mail="season1@example.com")
    user = session.exec(select(User).where(User.login == "season1")).first()
    season = ensure_season_seeded(session)

    session.add(PointsLog(uid=user.id, points=100, time=_now()))
    session.add(PointsLog(uid=user.id, points=50, time=_now()))
    session.commit()

    assert season_xp_for_user(session, user.id, season) == 150


def test_claim_new_steps_awards_coins_and_marks_claimed(client, session):
    register_user(client, login="season2", mail="season2@example.com")
    user = session.exec(select(User).where(User.login == "season2")).first()
    season = ensure_season_seeded(session)

    session.add(PointsLog(uid=user.id, points=XP_PER_STEP * 3, time=_now()))
    session.commit()

    granted = claim_new_steps(session, user, season)
    assert len(granted) == 3
    assert claimed_max_step(session, user.id, season.id) == 3


def test_claim_new_steps_does_not_regrant_already_claimed(client, session):
    register_user(client, login="season3", mail="season3@example.com")
    user = session.exec(select(User).where(User.login == "season3")).first()
    season = ensure_season_seeded(session)

    session.add(PointsLog(uid=user.id, points=XP_PER_STEP * 2, time=_now()))
    session.commit()
    first = claim_new_steps(session, user, season)
    assert len(first) == 2

    second = claim_new_steps(session, user, season)
    assert second == []  # без новых XP — ничего нового не выдаётся


def test_claim_new_steps_grants_item_at_step_5(client, session):
    register_user(client, login="season4", mail="season4@example.com")
    user = session.exec(select(User).where(User.login == "season4")).first()
    season = ensure_season_seeded(session)

    session.add(PointsLog(uid=user.id, points=XP_PER_STEP * 5, time=_now()))
    session.commit()

    claim_new_steps(session, user, season)
    assert is_owned(session, user.id, SEASON_ITEMS[0][0])


def test_hero_page_shows_season_progress(client, session):
    register_user(client, login="season5", mail="season5@example.com")
    resp = client.get("/hero")
    assert resp.status_code == 200
    assert "Сезон пробуждения" in resp.text
