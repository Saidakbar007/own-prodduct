"""Тесты системы мотивации: минимальная версия, адаптивный план, ставки, напарник, сундук."""

from datetime import datetime, timedelta, timezone

from sqlmodel import select

from app.models import Bet, Habit, HabitHistory, Level, Partnership, User
from app.services.adaptive_plan import apply_adaptive_plan, needs_adaptive_plan, weekly_completion_rate
from app.services.bets import evaluate_bet, place_bet
from app.services.chests import maybe_award_chest
from app.services.partnerships import combined_streak, evaluate_partnership
from app.routers.habits import _now
from tests.conftest import register_user


def test_minimal_version_extends_streak_with_fewer_points(client, session):
    register_user(client, login="kara", mail="kara@example.com")
    client.post("/habits", data={"name": "Марафон", "difficulty": "hard", "minimal_description": "5 минут", "sphere": "strength"})
    user = session.exec(select(User).where(User.login == "kara")).first()
    habit = session.exec(select(Habit).where(Habit.uid == user.id)).first()
    assert habit.point == 20

    resp = client.post(f"/habits/{habit.id}/check", data={"kind": "minimal"})
    assert resp.status_code == 200

    entry = session.exec(select(HabitHistory).where(HabitHistory.h_id == habit.id)).first()
    assert entry.kind == "minimal"

    level = session.exec(select(Level).where(Level.uid == user.id)).first()
    assert level.point == 10  # половина от 20


def test_adaptive_plan_suggested_below_50_percent(client, session):
    register_user(client, login="liam2", mail="liam2@example.com")
    client.post("/habits", data={"name": "Чтение", "sphere": "health"})
    user = session.exec(select(User).where(User.login == "liam2")).first()
    habit = session.exec(select(Habit).where(Habit.uid == user.id)).first()

    # Отмечено только 1 день из последних 7 — явно меньше 50%
    session.add(HabitHistory(h_id=habit.id, time=_now(), kind="done"))
    session.commit()

    assert needs_adaptive_plan(session, habit) is True
    assert weekly_completion_rate(session, habit) < 0.5

    apply_adaptive_plan(session, habit)
    session.refresh(habit)
    assert habit.frequency == "weekly"
    assert habit.weekdays == "0,2,4"


def test_bet_win_doubles_stake(client, session):
    register_user(client, login="mona", mail="mona@example.com")
    client.post("/habits", data={"name": "Бег", "sphere": "health"})
    user = session.exec(select(User).where(User.login == "mona")).first()
    habit = session.exec(select(Habit).where(Habit.uid == user.id)).first()

    level = session.exec(select(Level).where(Level.uid == user.id)).first()
    level.point = 100
    session.add(level)
    session.commit()

    from datetime import date

    bet = place_bet(session, user, habit, stake_points=30, target_days=3)
    assert bet is not None
    session.refresh(level)
    assert level.point == 70  # 100 - 30 списано сразу

    for days_ago in range(2, -1, -1):
        session.add(HabitHistory(h_id=habit.id, time=_now() - timedelta(days=days_ago), kind="done"))
    session.commit()

    bet.start_date = date.today() - timedelta(days=2)
    session.add(bet)
    session.commit()

    evaluate_bet(session, bet)
    session.refresh(bet)
    assert bet.status == "won"

    session.refresh(level)
    assert level.point == 70 + 60  # +30*2


def test_bet_lost_when_day_missed(client, session):
    register_user(client, login="nora", mail="nora@example.com")
    client.post("/habits", data={"name": "Бег", "sphere": "health"})
    user = session.exec(select(User).where(User.login == "nora")).first()
    habit = session.exec(select(Habit).where(Habit.uid == user.id)).first()

    level = session.exec(select(Level).where(Level.uid == user.id)).first()
    level.point = 50
    session.add(level)
    session.commit()

    from datetime import date

    bet = place_bet(session, user, habit, stake_points=20, target_days=5)
    bet.start_date = date.today() - timedelta(days=3)
    session.add(bet)
    session.commit()

    # отметили только день начала ставки, остальные дни пропущены
    session.add(HabitHistory(h_id=habit.id, time=_now() - timedelta(days=3), kind="done"))
    session.commit()

    evaluate_bet(session, bet)
    session.refresh(bet)
    assert bet.status == "lost"


def test_cannot_bet_more_points_than_available(client, session):
    register_user(client, login="omar", mail="omar@example.com")
    client.post("/habits", data={"name": "Бег", "sphere": "health"})
    user = session.exec(select(User).where(User.login == "omar")).first()
    habit = session.exec(select(Habit).where(Habit.uid == user.id)).first()

    bet = place_bet(session, user, habit, stake_points=99999, target_days=3)
    assert bet is None


def test_partnership_proposal_accept_and_break(client, session):
    register_user(client, login="priya", mail="priya@example.com")
    client.post("/habits", data={"name": "Бег", "sphere": "health"})
    client.get("/logout")
    register_user(client, login="quin", mail="quin@example.com")
    client.post("/habits", data={"name": "Йога", "sphere": "health"})
    client.get("/logout")

    client.post("/login", data={"login": "priya", "password": "secret123"})
    client.post("/friends/request", data={"login": "quin"})
    client.get("/logout")

    from app.models import Friend

    client.post("/login", data={"login": "quin", "password": "secret123"})
    pending = session.exec(select(Friend).where(Friend.status == "pending")).first()
    client.post(f"/friends/{pending.id}/accept")

    priya = session.exec(select(User).where(User.login == "priya")).first()
    quin = session.exec(select(User).where(User.login == "quin")).first()
    priya_habit = session.exec(select(Habit).where(Habit.uid == priya.id)).first()
    quin_habit = session.exec(select(Habit).where(Habit.uid == quin.id)).first()
    client.get("/logout")

    client.post("/login", data={"login": "priya", "password": "secret123"})
    client.post(f"/habits/{priya_habit.id}/partnership", data={"friend_login": "quin"})
    client.get("/logout")

    client.post("/login", data={"login": "quin", "password": "secret123"})
    partnership = session.exec(select(Partnership).where(Partnership.status == "pending")).first()
    assert partnership is not None
    client.post(f"/partnerships/{partnership.id}/accept", data={"habit_id": quin_habit.id})

    session.refresh(partnership)
    assert partnership.status == "active"

    # оба отметили сегодня — общая серия = 1
    session.add(HabitHistory(h_id=priya_habit.id, time=_now(), kind="done"))
    session.add(HabitHistory(h_id=quin_habit.id, time=_now(), kind="done"))
    session.commit()
    assert combined_streak(session, partnership) == 1

    # теперь у priya серия обрывается (нет вчерашней отметки, а до этого был разрыв)
    evaluate_partnership(session, partnership)  # оба со streak>=1 — партнёрство живо
    session.refresh(partnership)
    assert partnership.status == "active"


def test_chest_awarded_for_full_week(client, session, monkeypatch):
    import app.services.chests as chests_module

    register_user(client, login="rex", mail="rex@example.com")
    client.post("/habits", data={"name": "Бег", "sphere": "health"})
    user = session.exec(select(User).where(User.login == "rex")).first()
    habit = session.exec(select(Habit).where(Habit.uid == user.id)).first()

    from datetime import date

    monday = date(2026, 1, 12)
    sunday = monday + timedelta(days=6)

    class FakeDate(date):
        @classmethod
        def today(cls):
            return sunday

    monkeypatch.setattr(chests_module, "date", FakeDate)

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

    chest = maybe_award_chest(session, user, habit)
    assert chest is not None
    assert chest.reward_type in ("points", "freeze", "badge")

    # повторный вызов в ту же неделю не выдаёт сундук снова
    chest_again = maybe_award_chest(session, user, habit)
    assert chest_again is None
