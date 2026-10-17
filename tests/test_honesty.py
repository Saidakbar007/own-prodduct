"""
Интеграционные тесты системы честности: честный пропуск, фото-доказательство,
подтверждение другом.
"""

import io
from datetime import datetime, timedelta, timezone

from sqlmodel import select

from app.models import Habit, HabitConfirmation, HabitHistory, Level, User
from tests.conftest import register_user


def _create_habit(client, **extra):
    data = {"name": "Бег", "difficulty": "medium", "sphere": "strength"}
    data.update(extra)
    return client.post("/habits", data=data)


def test_honest_skip_awards_small_bonus_but_no_streak(client, session):
    register_user(client, login="elle", mail="elle@example.com")
    _create_habit(client)
    user = session.exec(select(User).where(User.login == "elle")).first()
    habit = session.exec(select(Habit).where(Habit.uid == user.id)).first()

    resp = client.post(f"/habits/{habit.id}/check", data={"kind": "skip"})
    assert resp.status_code == 200
    assert "честность" in resp.text

    entry = session.exec(select(HabitHistory).where(HabitHistory.h_id == habit.id)).first()
    assert entry.kind == "skip"

    level = session.exec(select(Level).where(Level.uid == user.id)).first()
    assert level.point == 2


def test_requires_proof_blocks_check_without_photo(client, session):
    register_user(client, login="finn2", mail="finn2@example.com")
    _create_habit(client, requires_proof="1")
    user = session.exec(select(User).where(User.login == "finn2")).first()
    habit = session.exec(select(Habit).where(Habit.uid == user.id)).first()
    assert habit.requires_proof is True

    resp = client.post(f"/habits/{habit.id}/check", data={"kind": "done"})
    assert resp.status_code == 400
    assert "фото-доказательство" in resp.text

    history = session.exec(select(HabitHistory).where(HabitHistory.h_id == habit.id)).all()
    assert history == []


def test_check_with_proof_photo_saves_path(client, session, tmp_path, monkeypatch):
    import app.services.uploads as uploads_module

    monkeypatch.setattr(uploads_module, "UPLOADS_DIR", str(tmp_path / "uploads"))

    register_user(client, login="gail", mail="gail@example.com")
    _create_habit(client, requires_proof="1")
    user = session.exec(select(User).where(User.login == "gail")).first()
    habit = session.exec(select(Habit).where(Habit.uid == user.id)).first()

    photo = io.BytesIO(b"fake-image-bytes")
    resp = client.post(
        f"/habits/{habit.id}/check",
        data={"kind": "done"},
        files={"proof": ("proof.jpg", photo, "image/jpeg")},
    )
    assert resp.status_code == 200

    entry = session.exec(select(HabitHistory).where(HabitHistory.h_id == habit.id)).first()
    assert entry.proof_path is not None

    import os

    assert os.path.exists(entry.proof_path)


def test_friend_confirmation_awards_coins_but_never_xp(client, session):
    register_user(client, login="hugo3", mail="hugo3@example.com")
    _create_habit(client)
    client.get("/logout")
    register_user(client, login="ivy2", mail="ivy2@example.com")
    client.get("/logout")

    client.post("/login", data={"login": "hugo3", "password": "secret123"})
    client.post("/friends/request", data={"login": "ivy2"})
    client.get("/logout")

    from app.models import Friend

    client.post("/login", data={"login": "ivy2", "password": "secret123"})
    pending = session.exec(select(Friend).where(Friend.status == "pending")).first()
    client.post(f"/friends/{pending.id}/accept")
    client.get("/logout")

    # дружба старше 7 дней — иначе анти-сговор заблокирует подтверждение
    friend = session.exec(select(Friend).where(Friend.id == pending.id)).first()
    friend.update_date = datetime.now(timezone.utc) - timedelta(days=8)
    session.add(friend)
    session.commit()

    client.post("/login", data={"login": "hugo3", "password": "secret123"})
    hugo = session.exec(select(User).where(User.login == "hugo3")).first()
    habit = session.exec(select(Habit).where(Habit.uid == hugo.id)).first()
    photo = io.BytesIO(b"fake-image-bytes")
    client.post(
        f"/habits/{habit.id}/check",
        data={"kind": "done"},
        files={"proof": ("proof.jpg", photo, "image/jpeg")},
    )
    entry = session.exec(select(HabitHistory).where(HabitHistory.h_id == habit.id)).first()
    hugo_level_before = session.exec(select(Level).where(Level.uid == hugo.id)).first()
    hugo_points_before = hugo_level_before.point
    client.get("/logout")

    client.post("/login", data={"login": "ivy2", "password": "secret123"})
    ivy = session.exec(select(User).where(User.login == "ivy2")).first()
    ivy_coins_before = ivy.coins
    hugo_coins_before = session.exec(select(User).where(User.id == hugo.id)).first().coins
    resp = client.post(f"/confirmations/{entry.id}/confirm")
    assert resp.status_code == 200

    confirmation = session.exec(select(HabitConfirmation).where(HabitConfirmation.history_id == entry.id)).first()
    assert confirmation.status == "confirmed"

    session.refresh(ivy)
    session.refresh(hugo)
    ivy_level = session.exec(select(Level).where(Level.uid == ivy.id)).first()
    hugo_level = session.exec(select(Level).where(Level.uid == hugo.id)).first()
    # дельта от самого подтверждения — монетами (без trust-множителя), не XP;
    # абсолютные суммы не берём, т.к. к этому моменту уже могли начислиться
    # монеты за другие события (достижения "первая привычка"/"первый друг" и т.п.)
    assert ivy.coins - ivy_coins_before == 1  # бонус подтверждающему
    assert hugo.coins - hugo_coins_before == 3  # бонус владельцу
    assert ivy_level.point == 0  # подтверждение не даёт XP
    assert hugo_level.point == hugo_points_before  # XP не изменился от подтверждения


def test_cannot_confirm_own_checkin(client, session):
    register_user(client, login="jack2", mail="jack2@example.com")
    _create_habit(client)
    user = session.exec(select(User).where(User.login == "jack2")).first()
    habit = session.exec(select(Habit).where(Habit.uid == user.id)).first()
    client.post(f"/habits/{habit.id}/check", data={"kind": "done"})
    entry = session.exec(select(HabitHistory).where(HabitHistory.h_id == habit.id)).first()

    resp = client.post(f"/confirmations/{entry.id}/confirm")
    assert resp.status_code == 404

    confirmation = session.exec(select(HabitConfirmation)).first()
    assert confirmation is None
