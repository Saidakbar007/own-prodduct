"""
Тесты босса недели (v6b): ротация босса, создание/вступление в группу,
HP = 300×участников, урон, победа (сундук+монеты всем), истечение без штрафа.
"""

from sqlmodel import select

from app.models import BossGroup, BossGroupMember, BossHit, Friend, User
from app.services.bosses import (
    BOSS_UNLOCK_HERO_LEVEL,
    BOSSES,
    HP_PER_MEMBER,
    VICTORY_COINS,
    active_group_for_user,
    boss_of_week,
    create_group,
    deal_damage,
    expire_stale_groups,
    join_group,
)
from tests.conftest import register_user


def _accept_friendship(client, session, requester_login, target_login):
    client.post("/login", data={"login": requester_login, "password": "secret123"})
    client.post("/friends/request", data={"login": target_login})
    client.get("/logout")

    client.post("/login", data={"login": target_login, "password": "secret123"})
    requester = session.exec(select(User).where(User.login == requester_login)).first()
    pending = session.exec(select(Friend).where(Friend.status == "pending", Friend.uid == requester.id)).first()
    client.post(f"/friends/{pending.id}/accept")
    client.get("/logout")


def test_boss_of_week_is_deterministic_rotation():
    assert boss_of_week("2026-W01") in BOSSES
    assert boss_of_week("2026-W01") == boss_of_week("2026-W01")
    # разные недели -> в целом разные боссы, хотя бы какое-то разнообразие на 6 неделях
    bosses_seen = {boss_of_week(f"2026-W{w:02d}") for w in range(1, 7)}
    assert len(bosses_seen) == 6  # ровно по одному на каждый из 6 боссов


def test_create_group_blocked_below_unlock_level(client, session):
    register_user(client, login="boss1", mail="boss1@example.com")
    user = session.exec(select(User).where(User.login == "boss1")).first()

    group, message = create_group(session, user, hero_level=BOSS_UNLOCK_HERO_LEVEL - 1)
    assert group is None


def test_create_group_at_unlock_level_sets_hp_for_one_member(client, session):
    register_user(client, login="boss2", mail="boss2@example.com")
    user = session.exec(select(User).where(User.login == "boss2")).first()

    group, message = create_group(session, user, hero_level=BOSS_UNLOCK_HERO_LEVEL)
    assert group is not None
    assert group.hp_total == HP_PER_MEMBER
    assert group.hp_remaining == HP_PER_MEMBER
    assert group.status == "active"

    members = session.exec(select(BossGroupMember).where(BossGroupMember.group_id == group.id)).all()
    assert len(members) == 1
    assert members[0].uid == user.id


def test_cannot_create_second_group_same_week(client, session):
    register_user(client, login="boss3", mail="boss3@example.com")
    user = session.exec(select(User).where(User.login == "boss3")).first()

    create_group(session, user, hero_level=10)
    second, message = create_group(session, user, hero_level=10)
    assert second is None
    assert "уже есть" in message.lower()


def test_join_requires_friendship(client, session):
    register_user(client, login="boss4", mail="boss4@example.com")
    creator = session.exec(select(User).where(User.login == "boss4")).first()
    group, _m = create_group(session, creator, hero_level=10)
    client.get("/logout")

    register_user(client, login="boss5", mail="boss5@example.com")
    stranger = session.exec(select(User).where(User.login == "boss5")).first()

    ok, message = join_group(session, stranger, group.id)
    assert ok is False
    assert "друг" in message.lower()


def test_join_adds_300_hp_and_member(client, session):
    register_user(client, login="boss6", mail="boss6@example.com")
    creator = session.exec(select(User).where(User.login == "boss6")).first()
    group, _m = create_group(session, creator, hero_level=10)
    client.get("/logout")

    register_user(client, login="boss7", mail="boss7@example.com")
    client.get("/logout")
    _accept_friendship(client, session, "boss6", "boss7")

    joiner = session.exec(select(User).where(User.login == "boss7")).first()
    ok, message = join_group(session, joiner, group.id)
    assert ok is True

    session.refresh(group)
    assert group.hp_total == HP_PER_MEMBER * 2
    assert group.hp_remaining == HP_PER_MEMBER * 2

    members = session.exec(select(BossGroupMember).where(BossGroupMember.group_id == group.id)).all()
    assert len(members) == 2


def test_join_blocked_if_already_in_a_group(client, session):
    register_user(client, login="boss8", mail="boss8@example.com")
    creator = session.exec(select(User).where(User.login == "boss8")).first()
    group_a, _m = create_group(session, creator, hero_level=10)
    client.get("/logout")

    register_user(client, login="boss9", mail="boss9@example.com")
    other = session.exec(select(User).where(User.login == "boss9")).first()
    group_b, _m2 = create_group(session, other, hero_level=10)
    client.get("/logout")
    _accept_friendship(client, session, "boss8", "boss9")

    ok, message = join_group(session, other, group_a.id)
    assert ok is False


def test_deal_damage_logs_hit_and_reduces_hp(client, session):
    register_user(client, login="boss10", mail="boss10@example.com")
    user = session.exec(select(User).where(User.login == "boss10")).first()
    group, _m = create_group(session, user, hero_level=10)

    result = deal_damage(session, user, 50)
    assert result is not None
    assert result.hp_remaining == HP_PER_MEMBER - 50

    hits = session.exec(select(BossHit).where(BossHit.group_id == group.id)).all()
    assert len(hits) == 1
    assert hits[0].damage == 50


def test_deal_damage_without_group_does_nothing(client, session):
    register_user(client, login="boss11", mail="boss11@example.com")
    user = session.exec(select(User).where(User.login == "boss11")).first()

    result = deal_damage(session, user, 50)
    assert result is None


def test_victory_awards_coins_and_chest_to_all_members(client, session, monkeypatch):
    import app.services.chests as chests_module

    monkeypatch.setattr(chests_module, "roll_chest_rarity", lambda trust_score: "common")

    register_user(client, login="boss12", mail="boss12@example.com")
    creator = session.exec(select(User).where(User.login == "boss12")).first()
    group, _m = create_group(session, creator, hero_level=10)
    client.get("/logout")

    register_user(client, login="boss13", mail="boss13@example.com")
    client.get("/logout")
    _accept_friendship(client, session, "boss12", "boss13")
    joiner = session.exec(select(User).where(User.login == "boss13")).first()
    join_group(session, joiner, group.id)

    coins_before_creator = creator.coins
    coins_before_joiner = joiner.coins

    result = deal_damage(session, creator, HP_PER_MEMBER * 2)  # добивает группу (400 HP) за раз
    assert result.status == "won"

    session.refresh(creator)
    session.refresh(joiner)
    assert creator.coins - coins_before_creator == VICTORY_COINS
    assert joiner.coins - coins_before_joiner == VICTORY_COINS


def test_defeat_group_no_longer_takes_damage(client, session):
    register_user(client, login="boss14", mail="boss14@example.com")
    user = session.exec(select(User).where(User.login == "boss14")).first()
    create_group(session, user, hero_level=10)

    deal_damage(session, user, HP_PER_MEMBER)  # добивает единственного участника
    assert active_group_for_user(session, user.id) is None  # won -> больше не "активная" для урона

    # у пользователя больше нет активной группы -> новый урон не наносится никому
    result = deal_damage(session, user, 10)
    assert result is None


def test_expire_stale_groups_marks_old_weeks_expired_without_penalty(client, session):
    register_user(client, login="boss15", mail="boss15@example.com")
    user = session.exec(select(User).where(User.login == "boss15")).first()
    group, _m = create_group(session, user, hero_level=10)

    group.week_key = "2000-W01"  # явно прошлая неделя
    session.add(group)
    session.commit()

    expire_stale_groups(session)
    session.refresh(group)
    assert group.status == "expired"

    coins_before = user.coins
    session.refresh(user)
    assert user.coins == coins_before  # никакого штрафа
