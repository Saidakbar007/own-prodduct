"""
Тесты изоляции тестовых аккаунтов (v6d, DECISIONS.md п.19): is_test не
попадает в рейтинг друзей, не затягивает друзей в бой с "ненастоящим" HP,
не может ни подтверждать чужие отметки, ни быть подтверждённым.
"""

from sqlmodel import select

from app.models import Friend, Habit, HabitHistory, User
from app.services.bosses import create_group, join_group, joinable_groups_for_user
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


def test_is_test_user_excluded_from_friends_leaderboard(client, session):
    register_user(client, login="real1", mail="real1@example.com")
    register_user(client, login="testacc1", mail="testacc1@example.com")
    _accept_friendship(client, session, "real1", "testacc1")

    test_user = session.exec(select(User).where(User.login == "testacc1")).first()
    test_user.is_test = True
    session.add(test_user)
    session.commit()

    client.post("/login", data={"login": "real1", "password": "secret123"})
    resp = client.get("/friends")
    assert "testacc1" not in resp.text


def test_joinable_groups_hide_all_test_group(client, session):
    register_user(client, login="real2", mail="real2@example.com")
    register_user(client, login="testacc2", mail="testacc2@example.com")
    _accept_friendship(client, session, "real2", "testacc2")

    test_user = session.exec(select(User).where(User.login == "testacc2")).first()
    test_user.is_test = True
    session.add(test_user)
    session.commit()

    group, _ = create_group(session, test_user, hero_level=10)
    assert group is not None

    real_user = session.exec(select(User).where(User.login == "real2")).first()
    joinable = joinable_groups_for_user(session, real_user.id)
    assert all(g.id != group.id for g in joinable)


def test_joinable_groups_keep_mixed_group_with_real_member(client, session):
    register_user(client, login="real3", mail="real3@example.com")
    register_user(client, login="real3b", mail="real3b@example.com")
    register_user(client, login="testacc3", mail="testacc3@example.com")
    _accept_friendship(client, session, "real3", "real3b")
    _accept_friendship(client, session, "real3", "testacc3")

    real3b = session.exec(select(User).where(User.login == "real3b")).first()
    group, _ = create_group(session, real3b, hero_level=10)
    assert group is not None

    test_user = session.exec(select(User).where(User.login == "testacc3")).first()
    test_user.is_test = True
    session.add(test_user)
    session.commit()

    real3 = session.exec(select(User).where(User.login == "real3")).first()
    joinable = joinable_groups_for_user(session, real3.id)
    assert any(g.id == group.id for g in joinable)


def _habit_with_proof_checkin(session, owner):
    habit = Habit(uid=owner.id, name="Пробежка", point=10, story_point=1.0, sphere="strength")
    session.add(habit)
    session.commit()
    session.refresh(habit)
    entry = HabitHistory(h_id=habit.id, kind="done", proof_path="proof.jpg")
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return habit, entry


def test_test_account_owner_cannot_be_confirmed(client, session):
    register_user(client, login="real4", mail="real4@example.com")
    register_user(client, login="testacc4", mail="testacc4@example.com")
    _accept_friendship(client, session, "real4", "testacc4")

    owner = session.exec(select(User).where(User.login == "testacc4")).first()
    owner.is_test = True
    session.add(owner)
    session.commit()
    _, entry = _habit_with_proof_checkin(session, owner)

    client.post("/login", data={"login": "real4", "password": "secret123"})
    resp = client.post(f"/confirmations/{entry.id}/confirm")
    assert resp.status_code == 404


def test_test_account_cannot_confirm_others(client, session):
    register_user(client, login="real5", mail="real5@example.com")
    register_user(client, login="testacc5", mail="testacc5@example.com")
    _accept_friendship(client, session, "real5", "testacc5")

    confirmer = session.exec(select(User).where(User.login == "testacc5")).first()
    confirmer.is_test = True
    session.add(confirmer)
    session.commit()

    owner = session.exec(select(User).where(User.login == "real5")).first()
    _, entry = _habit_with_proof_checkin(session, owner)

    client.post("/login", data={"login": "testacc5", "password": "secret123"})
    resp = client.post(f"/confirmations/{entry.id}/confirm")
    assert resp.status_code == 404
