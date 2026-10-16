"""Тесты trust score: доля отметок с доказательством/подтверждением, штрафы."""

from datetime import datetime, timedelta, timezone

from sqlmodel import select

from app.models import Habit, HabitConfirmation, HabitHistory, User
from app.services.points import award_points
from app.services.trust import compute_trust_score, trust_multiplier
from tests.conftest import register_user


def test_new_user_has_full_trust_score(client, session):
    register_user(client, login="aiden", mail="aiden@example.com")
    user = session.exec(select(User).where(User.login == "aiden")).first()
    assert compute_trust_score(session, user.id) == 100


def test_proof_photo_raises_trust_score(client, session):
    register_user(client, login="blair", mail="blair@example.com")
    user = session.exec(select(User).where(User.login == "blair")).first()
    habit = Habit(uid=user.id, name="Бег")
    session.add(habit)
    session.commit()
    session.refresh(habit)

    now = datetime.now(timezone.utc)
    # 3 отметки без доказательств
    for i in range(3):
        session.add(HabitHistory(h_id=habit.id, time=now - timedelta(days=i), kind="done"))
    session.commit()
    score_without_proof = compute_trust_score(session, user.id)
    assert score_without_proof == 0  # ни одна отметка не подтверждена

    # ещё одна отметка — с доказательством
    session.add(HabitHistory(h_id=habit.id, time=now - timedelta(days=3), kind="done", proof_path="uploads/x.jpg"))
    session.commit()
    score_with_proof = compute_trust_score(session, user.id)
    assert score_with_proof > score_without_proof


def test_burst_checkins_penalize_trust_score(client, session):
    register_user(client, login="casey", mail="casey@example.com")
    user = session.exec(select(User).where(User.login == "casey")).first()
    habit = Habit(uid=user.id, name="Бег")
    session.add(habit)
    session.commit()
    session.refresh(habit)

    base = datetime.now(timezone.utc)
    # 5 отметок за 10 секунд — похоже на массовую подделку
    for i in range(5):
        session.add(
            HabitHistory(
                h_id=habit.id, time=base + timedelta(seconds=i * 2), kind="done", proof_path="uploads/x.jpg"
            )
        )
    session.commit()
    score = compute_trust_score(session, user.id)
    assert score < 100  # штраф применён несмотря на 100% доказательств


def test_trust_multiplier_scales_points():
    assert trust_multiplier(100) == 1.0
    assert trust_multiplier(0) == 0.5
    assert trust_multiplier(50) == 0.75


def test_low_trust_score_reduces_awarded_points(client, session):
    register_user(client, login="drew", mail="drew@example.com")
    user = session.exec(select(User).where(User.login == "drew")).first()
    user.trust_score = 0
    session.add(user)
    session.commit()

    level, _ = award_points(session, user, 20)
    assert level.point == 10  # 20 * 0.5
