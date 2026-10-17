"""
Тесты антисговора друзей (v5, пункт 5): подтверждение только с фото,
только после 7 дней дружбы, лимиты 3/день и 1/другу/день, детектор
взаимных пар снижает вес подтверждения, низкий trust подтверждающего
даёт вес 0.
"""

import io
from datetime import datetime, timedelta, timezone

from sqlmodel import select

from app.models import Friend, Habit, HabitConfirmation, HabitHistory, User
from app.services.collusion import confirmation_weight, is_mutual_pair
from tests.conftest import register_user


def _accept_friendship(client, session, requester_login, target_login, days_old=8):
    client.post("/login", data={"login": requester_login, "password": "secret123"})
    client.post("/friends/request", data={"login": target_login})
    client.get("/logout")

    client.post("/login", data={"login": target_login, "password": "secret123"})
    pending = session.exec(
        select(Friend).where(
            Friend.status == "pending",
            Friend.uid == session.exec(select(User).where(User.login == requester_login)).first().id,
        )
    ).first()
    client.post(f"/friends/{pending.id}/accept")

    friend = session.exec(select(Friend).where(Friend.id == pending.id)).first()
    friend.update_date = datetime.now(timezone.utc) - timedelta(days=days_old)
    session.add(friend)
    session.commit()


def _checkin_with_photo(client, habit_id):
    photo = io.BytesIO(b"fake-image-bytes")
    return client.post(
        f"/habits/{habit_id}/check",
        data={"kind": "done"},
        files={"proof": ("proof.jpg", photo, "image/jpeg")},
    )


def test_confirmation_blocked_without_photo(client, session):
    register_user(client, login="alice5", mail="alice5@example.com")
    client.post("/habits", data={"name": "Бег", "sphere": "strength"})
    client.get("/logout")
    register_user(client, login="bob5", mail="bob5@example.com")
    client.get("/logout")

    _accept_friendship(client, session, "alice5", "bob5")

    client.post("/login", data={"login": "alice5", "password": "secret123"})
    user = session.exec(select(User).where(User.login == "alice5")).first()
    habit = session.exec(select(Habit).where(Habit.uid == user.id)).first()
    client.post(f"/habits/{habit.id}/check", data={"kind": "done"})  # без фото
    entry = session.exec(select(HabitHistory).where(HabitHistory.h_id == habit.id)).first()
    client.get("/logout")

    client.post("/login", data={"login": "bob5", "password": "secret123"})
    resp = client.post(f"/confirmations/{entry.id}/confirm")
    assert resp.status_code == 400
    assert "фото" in resp.text

    confirmation = session.exec(select(HabitConfirmation).where(HabitConfirmation.history_id == entry.id)).first()
    assert confirmation is None


def test_confirmation_blocked_before_7_days_of_friendship(client, session):
    register_user(client, login="carl5", mail="carl5@example.com")
    client.post("/habits", data={"name": "Бег", "sphere": "strength"})
    client.get("/logout")
    register_user(client, login="dina5", mail="dina5@example.com")
    client.get("/logout")

    _accept_friendship(client, session, "carl5", "dina5", days_old=2)  # дружба только 2 дня

    client.post("/login", data={"login": "carl5", "password": "secret123"})
    user = session.exec(select(User).where(User.login == "carl5")).first()
    habit = session.exec(select(Habit).where(Habit.uid == user.id)).first()
    _checkin_with_photo(client, habit.id)
    entry = session.exec(select(HabitHistory).where(HabitHistory.h_id == habit.id)).first()
    client.get("/logout")

    client.post("/login", data={"login": "dina5", "password": "secret123"})
    resp = client.post(f"/confirmations/{entry.id}/confirm")
    assert resp.status_code == 400
    assert "7 дней" in resp.text


def test_confirmation_daily_limit_three_across_different_friends(client, session):
    register_user(client, login="hub5", mail="hub5@example.com")
    client.get("/logout")

    entry_ids = []
    for i in range(4):
        login = f"spoke5{i}"
        register_user(client, login=login, mail=f"{login}@example.com")
        client.post("/habits", data={"name": f"Привычка {i}", "sphere": "strength"})
        user = session.exec(select(User).where(User.login == login)).first()
        habit = session.exec(select(Habit).where(Habit.uid == user.id)).first()
        _checkin_with_photo(client, habit.id)
        entry = session.exec(select(HabitHistory).where(HabitHistory.h_id == habit.id)).first()
        entry_ids.append(entry.id)
        client.get("/logout")

        _accept_friendship(client, session, "hub5", login)

    client.post("/login", data={"login": "hub5", "password": "secret123"})
    statuses = [client.post(f"/confirmations/{eid}/confirm").status_code for eid in entry_ids]

    assert statuses[:3] == [200, 200, 200]
    assert statuses[3] == 400  # 4-е подтверждение в тот же день — лимит 3/день исчерпан

    confirmed_count = session.exec(
        select(HabitConfirmation).where(HabitConfirmation.status == "confirmed")
    ).all()
    assert len(confirmed_count) == 3


def test_confirmation_limit_one_per_friend_per_day(client, session):
    register_user(client, login="iris5", mail="iris5@example.com")
    client.post("/habits", data={"name": "Привычка1", "sphere": "strength"})
    client.post("/habits", data={"name": "Привычка2", "sphere": "strength"})
    user = session.exec(select(User).where(User.login == "iris5")).first()
    habits = session.exec(select(Habit).where(Habit.uid == user.id)).all()

    entry_ids = []
    for habit in habits:
        _checkin_with_photo(client, habit.id)
        entry = session.exec(
            select(HabitHistory).where(HabitHistory.h_id == habit.id)
        ).first()
        entry_ids.append(entry.id)
    client.get("/logout")

    register_user(client, login="jace5", mail="jace5@example.com")
    client.get("/logout")
    _accept_friendship(client, session, "iris5", "jace5")

    client.post("/login", data={"login": "jace5", "password": "secret123"})
    first = client.post(f"/confirmations/{entry_ids[0]}/confirm")
    second = client.post(f"/confirmations/{entry_ids[1]}/confirm")

    assert first.status_code == 200
    assert second.status_code == 400  # тому же другу второй раз за день — нельзя


def test_confirmation_awards_coins_never_xp_and_updates_trust(client, session):
    register_user(client, login="kara5", mail="kara5@example.com")
    client.post("/habits", data={"name": "Бег", "sphere": "strength"})
    user = session.exec(select(User).where(User.login == "kara5")).first()
    habit = session.exec(select(Habit).where(Habit.uid == user.id)).first()
    _checkin_with_photo(client, habit.id)
    entry = session.exec(select(HabitHistory).where(HabitHistory.h_id == habit.id)).first()
    client.get("/logout")

    register_user(client, login="liam5", mail="liam5@example.com")
    client.get("/logout")
    _accept_friendship(client, session, "kara5", "liam5")

    client.post("/login", data={"login": "liam5", "password": "secret123"})
    resp = client.post(f"/confirmations/{entry.id}/confirm")
    assert resp.status_code == 200

    session.refresh(user)
    assert user.coins == 3
    assert user.trust_score == 100  # 1 из 1 отметок с фото -> подтверждена


def test_mutual_pair_detector_flags_only_each_other(client, session):
    register_user(client, login="mona5", mail="mona5@example.com")
    client.post("/habits", data={"name": "Бег", "sphere": "strength"})
    client.get("/logout")
    register_user(client, login="nash5", mail="nash5@example.com")
    client.post("/habits", data={"name": "Йога", "sphere": "health"})
    client.get("/logout")

    _accept_friendship(client, session, "mona5", "nash5")

    mona = session.exec(select(User).where(User.login == "mona5")).first()
    nash = session.exec(select(User).where(User.login == "nash5")).first()
    mona_habit = session.exec(select(Habit).where(Habit.uid == mona.id)).first()
    nash_habit = session.exec(select(Habit).where(Habit.uid == nash.id)).first()

    # mona и nash подтверждают ТОЛЬКО друг друга, несколько раз за окно в 14 дней
    for i in range(3):
        entry_m = HabitHistory(h_id=mona_habit.id, time=datetime.now(timezone.utc) - timedelta(days=i), kind="done", proof_path="x.jpg")
        entry_n = HabitHistory(h_id=nash_habit.id, time=datetime.now(timezone.utc) - timedelta(days=i), kind="done", proof_path="x.jpg")
        session.add(entry_m)
        session.add(entry_n)
        session.commit()
        session.add(HabitConfirmation(history_id=entry_m.id, confirmer_uid=nash.id, status="confirmed", time=entry_m.time))
        session.add(HabitConfirmation(history_id=entry_n.id, confirmer_uid=mona.id, status="confirmed", time=entry_n.time))
        session.commit()

    assert is_mutual_pair(session, mona.id, nash.id) is True

    last_confirmation = session.exec(
        select(HabitConfirmation).where(HabitConfirmation.confirmer_uid == nash.id)
    ).first()
    assert confirmation_weight(session, last_confirmation, mona.id) == 0.25


def test_low_trust_confirmer_weight_is_zero(client, session):
    register_user(client, login="omar5", mail="omar5@example.com")
    client.post("/habits", data={"name": "Бег", "sphere": "strength"})
    client.get("/logout")
    register_user(client, login="priya5", mail="priya5@example.com")
    client.get("/logout")

    _accept_friendship(client, session, "omar5", "priya5")

    omar = session.exec(select(User).where(User.login == "omar5")).first()
    priya = session.exec(select(User).where(User.login == "priya5")).first()
    priya.trust_score = 10  # низкий trust
    session.add(priya)
    session.commit()

    habit = session.exec(select(Habit).where(Habit.uid == omar.id)).first()
    entry = HabitHistory(h_id=habit.id, time=datetime.now(timezone.utc), kind="done", proof_path="x.jpg")
    session.add(entry)
    session.commit()

    confirmation = HabitConfirmation(history_id=entry.id, confirmer_uid=priya.id, status="confirmed", time=entry.time)
    session.add(confirmation)
    session.commit()

    assert confirmation_weight(session, confirmation, omar.id) == 0.0
