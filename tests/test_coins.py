"""
Тесты монет (v6a): trust-множитель, +10% за "гармонию", источники монет
за привычки/фото/ежедневные задания/достижения.
"""

from datetime import timedelta

from sqlmodel import select

from app.models import PointsLog, User
from app.routers.habits import _now
from app.services.coins import award_coins, coin_trust_multiplier, coins_for_achievement
from tests.conftest import register_user


def test_coin_trust_multiplier_tiers():
    assert coin_trust_multiplier(0) == 0.5
    assert coin_trust_multiplier(39) == 0.5
    assert coin_trust_multiplier(40) == 1.0
    assert coin_trust_multiplier(79) == 1.0
    assert coin_trust_multiplier(80) == 1.2
    assert coin_trust_multiplier(100) == 1.2


def test_award_coins_applies_trust_multiplier(client, session):
    register_user(client, login="coin1", mail="coin1@example.com")
    user = session.exec(select(User).where(User.login == "coin1")).first()
    user.trust_score = 30  # ниже 40 -> x0.5
    session.add(user)
    session.commit()

    awarded = award_coins(session, user, 10, apply_harmony=False)
    assert awarded == 5
    assert user.coins == 5


def test_award_coins_zero_or_negative_awards_nothing(client, session):
    register_user(client, login="coin2", mail="coin2@example.com")
    user = session.exec(select(User).where(User.login == "coin2")).first()

    assert award_coins(session, user, 0) == 0
    assert award_coins(session, user, -5) == 0
    assert user.coins == 0


def test_award_coins_harmony_bonus(client, session):
    register_user(client, login="coin3", mail="coin3@example.com")
    user = session.exec(select(User).where(User.login == "coin3")).first()
    # у всех 5 сфер есть активность за последние 7 дней -> гармония
    for sphere in ("strength", "intellect", "discipline", "health", "charisma"):
        session.add(PointsLog(uid=user.id, points=10, sphere=sphere, time=_now()))
    session.commit()

    awarded = award_coins(session, user, 10, apply_trust=False)
    assert awarded == 11  # round(10 * 1.10)


def test_award_coins_without_harmony_no_bonus(client, session):
    register_user(client, login="coin4", mail="coin4@example.com")
    user = session.exec(select(User).where(User.login == "coin4")).first()

    awarded = award_coins(session, user, 10, apply_trust=False)
    assert awarded == 10


def test_coins_for_achievement_tiers():
    assert coins_for_achievement("first_habit") == 20
    assert coins_for_achievement("streak_7") == 50
    assert coins_for_achievement("streak_30") == 100
    assert coins_for_achievement("unknown_code") == 20  # дефолт на неизвестный код


def test_habit_check_awards_coins_by_difficulty(client, session):
    from app.models import Habit, HabitHistory

    register_user(client, login="coin5", mail="coin5@example.com")
    client.post(
        "/habits",
        data={"source": "custom", "name": "Марафон", "sphere": "strength", "difficulty": "hard"},
    )
    user = session.exec(select(User).where(User.login == "coin5")).first()
    habit = session.exec(select(Habit).where(Habit.uid == user.id)).first()
    coins_before = user.coins  # уже есть монеты за достижение "первая привычка"

    client.post(f"/habits/{habit.id}/check", data={"kind": "done"})

    session.refresh(user)
    # сложность "hard" без фото -> 4 монеты (trust=100 -> x1.2 -> round(4.8)=5)
    assert user.coins - coins_before == 5


def test_habit_check_photo_adds_coin_bonus(client, session):
    import io

    from app.models import Habit

    register_user(client, login="coin6", mail="coin6@example.com")
    client.post("/habits", data={"source": "custom", "name": "Бег", "sphere": "strength", "difficulty": "easy"})
    user = session.exec(select(User).where(User.login == "coin6")).first()
    habit = session.exec(select(Habit).where(Habit.uid == user.id)).first()
    coins_before = user.coins

    photo = io.BytesIO(b"fake-image-bytes")
    client.post(
        f"/habits/{habit.id}/check",
        data={"kind": "done"},
        files={"proof": ("proof.jpg", photo, "image/jpeg")},
    )

    session.refresh(user)
    # "easy" = 1 монета + 1 за фото = 2, trust=100 -> x1.2 -> round(2.4)=2
    assert user.coins - coins_before == 2
