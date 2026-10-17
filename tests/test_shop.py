"""
Тесты магазина и инвентаря (v6a): покупка/экипировка, уровневые ограничения
эпических, лимит заморозки, легендарные не продаются, использование заморозки.
"""

from datetime import timedelta

from sqlmodel import select

from app.models import Habit, HabitHistory, ShopItem, User
from app.routers.habits import _now
from app.services.shop import (
    CATALOG,
    FREEZE_MAX_STOCK,
    buy_item,
    ensure_shop_seeded,
    equip_item,
    is_owned,
    use_freeze,
)
from tests.conftest import register_user


def test_catalog_counts_match_spec(session):
    ensure_shop_seeded(session)
    by_slot = {}
    for code, slot, rarity, name, price, image in CATALOG:
        by_slot.setdefault(slot, []).append((code, rarity, price))

    assert len(by_slot["bg"]) == 12
    assert len(by_slot["frame"]) == 12
    assert len(by_slot["title"]) == 10
    assert len(by_slot["effect"]) == 5
    assert len(by_slot["freeze"]) == 1

    for slot in ("bg", "frame", "title", "effect"):
        legendary = [c for c in by_slot[slot] if c[1] == "legendary"]
        assert all(price is None for _code, _rarity, price in legendary)


def test_ensure_shop_seeded_is_idempotent(session):
    ensure_shop_seeded(session)
    first_count = len(session.exec(select(ShopItem)).all())
    ensure_shop_seeded(session)
    second_count = len(session.exec(select(ShopItem)).all())
    assert first_count == second_count == len(CATALOG)


def test_buy_item_deducts_coins_and_adds_to_inventory(client, session):
    ensure_shop_seeded(session)
    register_user(client, login="shop1", mail="shop1@example.com")
    user = session.exec(select(User).where(User.login == "shop1")).first()
    user.coins = 100
    session.add(user)
    session.commit()

    ok, message = buy_item(session, user, "bg_dawn", hero_level=1)
    assert ok is True
    assert user.coins == 50
    assert is_owned(session, user.id, "bg_dawn")


def test_cannot_buy_without_enough_coins(client, session):
    ensure_shop_seeded(session)
    register_user(client, login="shop2", mail="shop2@example.com")
    user = session.exec(select(User).where(User.login == "shop2")).first()

    ok, message = buy_item(session, user, "bg_dawn", hero_level=1)
    assert ok is False
    assert "монет" in message.lower()
    assert not is_owned(session, user.id, "bg_dawn")


def test_cannot_buy_same_item_twice(client, session):
    ensure_shop_seeded(session)
    register_user(client, login="shop3", mail="shop3@example.com")
    user = session.exec(select(User).where(User.login == "shop3")).first()
    user.coins = 200
    session.add(user)
    session.commit()

    buy_item(session, user, "bg_dawn", hero_level=1)
    ok, message = buy_item(session, user, "bg_dawn", hero_level=1)
    assert ok is False


def test_legendary_item_not_purchasable(client, session):
    ensure_shop_seeded(session)
    register_user(client, login="shop4", mail="shop4@example.com")
    user = session.exec(select(User).where(User.login == "shop4")).first()
    user.coins = 10**6
    session.add(user)
    session.commit()

    ok, message = buy_item(session, user, "bg_legend", hero_level=50)
    assert ok is False
    assert "не продаётся" in message.lower()


def test_epic_item_requires_hero_level_20(client, session):
    ensure_shop_seeded(session)
    register_user(client, login="shop5", mail="shop5@example.com")
    user = session.exec(select(User).where(User.login == "shop5")).first()
    user.coins = 10**6
    session.add(user)
    session.commit()

    blocked, message = buy_item(session, user, "bg_volcano", hero_level=19)
    assert blocked is False
    assert "уровень" in message.lower()

    allowed, _message = buy_item(session, user, "bg_volcano", hero_level=20)
    assert allowed is True


def test_equip_requires_ownership(client, session):
    ensure_shop_seeded(session)
    register_user(client, login="shop6", mail="shop6@example.com")
    user = session.exec(select(User).where(User.login == "shop6")).first()

    ok, message = equip_item(session, user, "bg_dawn")
    assert ok is False
    assert "купить" in message.lower()


def test_equip_sets_user_field_for_correct_slot(client, session):
    ensure_shop_seeded(session)
    register_user(client, login="shop7", mail="shop7@example.com")
    user = session.exec(select(User).where(User.login == "shop7")).first()
    user.coins = 200
    session.add(user)
    session.commit()

    buy_item(session, user, "frame_simple", hero_level=1)
    ok, _message = equip_item(session, user, "frame_simple")
    assert ok is True
    session.refresh(user)
    assert user.equipped_frame == "frame_simple"
    assert user.equipped_bg is None


def test_freeze_purchase_capped_at_max_stock(client, session):
    ensure_shop_seeded(session)
    register_user(client, login="shop8", mail="shop8@example.com")
    user = session.exec(select(User).where(User.login == "shop8")).first()
    user.coins = 1000
    session.add(user)
    session.commit()

    for _ in range(FREEZE_MAX_STOCK):
        ok, _message = buy_item(session, user, "freeze", hero_level=1)
        assert ok is True

    blocked, message = buy_item(session, user, "freeze", hero_level=1)
    assert blocked is False
    assert "максимум" in message.lower()
    assert user.freeze_stock == FREEZE_MAX_STOCK


def test_shop_page_lists_items_and_buy_flow(client, session):
    register_user(client, login="shop9", mail="shop9@example.com")
    user = session.exec(select(User).where(User.login == "shop9")).first()
    user.coins = 100
    session.add(user)
    session.commit()

    resp = client.get("/shop")
    assert resp.status_code == 200
    assert "Рассвет" in resp.text

    buy_resp = client.post("/shop/buy/bg_dawn")
    assert buy_resp.status_code == 200

    equip_resp = client.post("/shop/equip/bg_dawn")
    assert equip_resp.status_code == 200
    assert "Надето" in equip_resp.text


def test_use_freeze_protects_missed_day_without_breaking_streak(client, session):
    register_user(client, login="shop10", mail="shop10@example.com")
    client.post("/habits", data={"source": "custom", "name": "Бег", "sphere": "strength"})
    user = session.exec(select(User).where(User.login == "shop10")).first()
    habit = session.exec(select(Habit).where(Habit.uid == user.id)).first()
    user.freeze_stock = 1
    session.add(user)
    session.commit()

    missed_day = (_now() - timedelta(days=2)).date()
    ok, message = use_freeze(session, user, habit, missed_day)
    assert ok is True
    session.refresh(user)
    assert user.freeze_stock == 0

    entry = session.exec(select(HabitHistory).where(HabitHistory.h_id == habit.id)).first()
    assert entry.kind == "skip"


def test_use_freeze_fails_without_stock(client, session):
    register_user(client, login="shop11", mail="shop11@example.com")
    client.post("/habits", data={"source": "custom", "name": "Бег", "sphere": "strength"})
    user = session.exec(select(User).where(User.login == "shop11")).first()
    habit = session.exec(select(Habit).where(Habit.uid == user.id)).first()

    ok, message = use_freeze(session, user, habit, (_now() - timedelta(days=2)).date())
    assert ok is False
    assert "нет" in message.lower()


def test_use_freeze_rejects_today_or_future(client, session):
    from app.services.usertime import today_for

    register_user(client, login="shop13", mail="shop13@example.com")
    client.post("/habits", data={"source": "custom", "name": "Бег", "sphere": "strength"})
    user = session.exec(select(User).where(User.login == "shop13")).first()
    habit = session.exec(select(Habit).where(Habit.uid == user.id)).first()
    user.freeze_stock = 1
    session.add(user)
    session.commit()

    today_ok, message_today = use_freeze(session, user, habit, today_for(user))
    assert today_ok is False
    assert "прошедш" in message_today.lower()

    future_ok, message_future = use_freeze(session, user, habit, today_for(user) + timedelta(days=1))
    assert future_ok is False


def test_use_freeze_route_rejects_day_with_existing_entry(client, session):
    register_user(client, login="shop12", mail="shop12@example.com")
    client.post("/habits", data={"source": "custom", "name": "Бег", "sphere": "strength"})
    user = session.exec(select(User).where(User.login == "shop12")).first()
    habit = session.exec(select(Habit).where(Habit.uid == user.id)).first()
    user.freeze_stock = 1
    session.add(user)
    session.commit()

    already_logged_day = (_now() - timedelta(days=1)).date()
    session.add(HabitHistory(h_id=habit.id, time=_now() - timedelta(days=1), kind="done"))
    session.commit()

    ok, message = use_freeze(session, user, habit, already_logged_day)
    assert ok is False
    assert "уже есть отметка" in message.lower()
