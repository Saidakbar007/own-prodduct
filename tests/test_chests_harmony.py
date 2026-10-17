"""
Тесты сундуков (v6b): вероятности редкости, бонус trust>=90 на легендарные,
"гармония" поднимает редкость на ступень, награды по редкости.
"""

from datetime import date, datetime, timedelta, timezone

from sqlmodel import select

from app.models import Chest, Habit, HabitHistory, Level, PointsLog, User
from app.services.chests import maybe_award_chest, roll_chest_rarity
from tests.conftest import register_user


def _make_full_week_habit(session, user) -> Habit:
    habit = Habit(uid=user.id, name="Бег", point=10, story_point=1.0, sphere="strength")
    session.add(habit)
    session.commit()
    session.refresh(habit)

    monday = date(2026, 1, 12)
    sunday = monday + timedelta(days=6)
    for i in range(7):
        day = monday + timedelta(days=i)
        session.add(
            HabitHistory(
                h_id=habit.id,
                time=datetime(day.year, day.month, day.day, 12, tzinfo=timezone.utc),
                kind="done",
            )
        )
    session.commit()
    return habit, sunday


def test_roll_chest_rarity_distribution_matches_weights():
    samples = 20000
    counts = {"common": 0, "rare": 0, "epic": 0, "legendary": 0}
    for _ in range(samples):
        counts[roll_chest_rarity(trust_score=50)] += 1

    total = samples
    assert 0.57 < counts["common"] / total < 0.63
    assert 0.25 < counts["rare"] / total < 0.31
    assert 0.07 < counts["epic"] / total < 0.13
    assert 0.01 < counts["legendary"] / total < 0.03


def test_high_trust_doubles_legendary_chance_at_cost_of_common():
    samples = 20000
    counts = {"common": 0, "legendary": 0}
    for _ in range(samples):
        rarity = roll_chest_rarity(trust_score=95)
        if rarity in counts:
            counts[rarity] += 1

    assert 0.03 < counts["legendary"] / samples < 0.05  # ~4%, было 2%
    assert 0.55 < counts["common"] / samples < 0.61  # ~58%, было 60%


def test_chest_reward_upgraded_one_rarity_with_harmony(client, session, monkeypatch):
    import app.services.chests as chests_module

    register_user(client, login="harmony1", mail="harmony1@example.com")
    user = session.exec(select(User).where(User.login == "harmony1")).first()
    habit, sunday = _make_full_week_habit(session, user)

    class FakeDate(date):
        @classmethod
        def today(cls):
            return sunday

    monkeypatch.setattr(chests_module, "date", FakeDate)
    monkeypatch.setattr(chests_module, "roll_chest_rarity", lambda trust_score: "common")

    for sphere in ("strength", "intellect", "discipline", "health", "charisma"):
        session.add(PointsLog(uid=user.id, points=1, sphere=sphere, time=datetime.now(timezone.utc)))
    session.commit()

    chest = maybe_award_chest(session, user, habit)
    assert chest is not None
    assert chest.rarity == "rare"  # common поднят на ступень гармонией


def test_chest_reward_not_upgraded_without_harmony(client, session, monkeypatch):
    import app.services.chests as chests_module

    register_user(client, login="harmony3", mail="harmony3@example.com")
    user = session.exec(select(User).where(User.login == "harmony3")).first()
    habit, sunday = _make_full_week_habit(session, user)

    class FakeDate(date):
        @classmethod
        def today(cls):
            return sunday

    monkeypatch.setattr(chests_module, "date", FakeDate)
    monkeypatch.setattr(chests_module, "roll_chest_rarity", lambda trust_score: "common")

    chest = maybe_award_chest(session, user, habit)
    assert chest is not None
    assert chest.rarity == "common"  # без гармонии — без повышения


def test_common_reward_grants_20_xp(client, session, monkeypatch):
    import app.services.chests as chests_module

    register_user(client, login="chestcoin1", mail="chestcoin1@example.com")
    user = session.exec(select(User).where(User.login == "chestcoin1")).first()
    habit, sunday = _make_full_week_habit(session, user)
    monkeypatch.setattr(chests_module, "date", type("D", (date,), {"today": classmethod(lambda cls: sunday)}))
    monkeypatch.setattr(chests_module, "roll_chest_rarity", lambda trust_score: "common")

    points_before = session.exec(select(Level).where(Level.uid == user.id)).first().point
    chest = maybe_award_chest(session, user, habit)

    level = session.exec(select(Level).where(Level.uid == user.id)).first()
    assert level.point - points_before == 20
    assert chest.reward_type == "points"
    assert chest.reward_value == "20"


def test_rare_reward_grants_freeze_stock_unless_full(client, session, monkeypatch):
    import app.services.chests as chests_module

    register_user(client, login="chestfreeze1", mail="chestfreeze1@example.com")
    user = session.exec(select(User).where(User.login == "chestfreeze1")).first()
    habit, sunday = _make_full_week_habit(session, user)
    monkeypatch.setattr(chests_module, "date", type("D", (date,), {"today": classmethod(lambda cls: sunday)}))
    monkeypatch.setattr(chests_module, "roll_chest_rarity", lambda trust_score: "rare")

    chest = maybe_award_chest(session, user, habit)
    session.refresh(user)
    assert chest.reward_type == "freeze"
    assert user.freeze_stock == 1


def test_rare_reward_falls_back_to_points_when_freeze_stock_full(client, session, monkeypatch):
    import app.services.chests as chests_module

    register_user(client, login="chestfreeze2", mail="chestfreeze2@example.com")
    user = session.exec(select(User).where(User.login == "chestfreeze2")).first()
    user.freeze_stock = 2
    session.add(user)
    session.commit()
    habit, sunday = _make_full_week_habit(session, user)
    monkeypatch.setattr(chests_module, "date", type("D", (date,), {"today": classmethod(lambda cls: sunday)}))
    monkeypatch.setattr(chests_module, "roll_chest_rarity", lambda trust_score: "rare")

    chest = maybe_award_chest(session, user, habit)
    session.refresh(user)
    assert chest.reward_type == "points"
    assert chest.reward_value == "40"
    assert user.freeze_stock == 2  # не превышен лимит


def test_legendary_reward_grants_xp_and_coins(client, session, monkeypatch):
    import app.services.chests as chests_module

    register_user(client, login="chestlegend1", mail="chestlegend1@example.com")
    user = session.exec(select(User).where(User.login == "chestlegend1")).first()
    habit, sunday = _make_full_week_habit(session, user)
    monkeypatch.setattr(chests_module, "date", type("D", (date,), {"today": classmethod(lambda cls: sunday)}))
    monkeypatch.setattr(chests_module, "roll_chest_rarity", lambda trust_score: "legendary")

    coins_before = user.coins
    chest = maybe_award_chest(session, user, habit)
    session.refresh(user)

    assert chest.reward_type == "badge"
    assert user.coins - coins_before == 36  # 30 монет * trust-множитель (100 -> x1.2)
