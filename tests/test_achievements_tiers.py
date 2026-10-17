"""
Тесты 3-тировых достижений (v6b): серии/сфера/честность/боссы/цели/
возвращения по бронзе/серебру/золоту + "все личности на стадии 5".
"""

from datetime import timedelta

from sqlmodel import select

from app.models import Habit, HabitConfirmation, HabitHistory, PointsLog, User
from app.routers.habits import _now
from app.services.achievements import (
    _comeback_count,
    _confirmed_marks_count,
    _max_sphere_level,
    check_and_award_achievements,
)
from app.services.coins import coins_for_achievement
from tests.conftest import register_user


def test_streak_gold_awarded_at_100_days(client, session):
    register_user(client, login="tier1", mail="tier1@example.com")
    user = session.exec(select(User).where(User.login == "tier1")).first()
    habit = Habit(uid=user.id, name="Бег", point=10, sphere="strength")
    session.add(habit)
    session.commit()
    session.refresh(habit)

    for days_ago in range(99, -1, -1):
        session.add(HabitHistory(h_id=habit.id, time=_now() - timedelta(days=days_ago), kind="done"))
    session.commit()

    earned = check_and_award_achievements(session, user)
    codes = {a.code for a in earned}
    assert {"streak_7", "streak_30", "streak_100"}.issubset(codes)


def test_sphere_tiers_use_max_across_spheres(client, session):
    register_user(client, login="tier2", mail="tier2@example.com")
    user = session.exec(select(User).where(User.login == "tier2")).first()

    # уровень сферы = 1 + xp//50; нужно 500 XP для уровня 11 (>=10, порог silver)
    session.add(PointsLog(uid=user.id, points=500, sphere="intellect", time=_now()))
    session.commit()

    assert _max_sphere_level(session, user.id) >= 10
    earned = check_and_award_achievements(session, user)
    codes = {a.code for a in earned}
    assert {"sphere_bronze", "sphere_silver"}.issubset(codes)
    assert "sphere_gold" not in codes


def test_honesty_confirmed_marks_counted_correctly(client, session):
    register_user(client, login="tier3", mail="tier3@example.com")
    owner = session.exec(select(User).where(User.login == "tier3")).first()
    habit = Habit(uid=owner.id, name="Бег", point=10, sphere="strength")
    session.add(habit)
    session.commit()
    session.refresh(habit)

    confirmed_entry = HabitHistory(h_id=habit.id, time=_now(), kind="done")
    unconfirmed_entry = HabitHistory(h_id=habit.id, time=_now() - timedelta(days=1), kind="done")
    session.add(confirmed_entry)
    session.add(unconfirmed_entry)
    session.commit()
    session.refresh(confirmed_entry)

    session.add(HabitConfirmation(history_id=confirmed_entry.id, confirmer_uid=owner.id, status="confirmed"))
    session.add(HabitConfirmation(history_id=unconfirmed_entry.id, confirmer_uid=owner.id, status="doubted"))
    session.commit()

    assert _confirmed_marks_count(session, owner.id) == 1


def test_comeback_count_requires_prior_activity_and_a_real_gap(client, session):
    register_user(client, login="tier4", mail="tier4@example.com")
    user = session.exec(select(User).where(User.login == "tier4")).first()
    habit = Habit(uid=user.id, name="Бег", point=10, sphere="strength")
    session.add(habit)
    session.commit()
    session.refresh(habit)

    today = _now()
    # день 10 назад: первая отметка (не возврат — нет предыдущей активности)
    session.add(HabitHistory(h_id=habit.id, time=today - timedelta(days=10), kind="done"))
    # день 9 назад: отметка сразу на следующий день — тоже не возврат (не было пропуска)
    session.add(HabitHistory(h_id=habit.id, time=today - timedelta(days=9), kind="done"))
    # день 7..8 назад пропущены (никакой отметки)
    # день 6 назад: возврат после пропуска -> это ВОЗВРАТ
    session.add(HabitHistory(h_id=habit.id, time=today - timedelta(days=6), kind="done"))
    session.commit()

    assert _comeback_count(session, user.id) == 1


def test_boss_bronze_awarded_after_first_victory(client, session):
    from app.services.bosses import HP_PER_MEMBER, create_group, deal_damage

    register_user(client, login="tier7", mail="tier7@example.com")
    user = session.exec(select(User).where(User.login == "tier7")).first()
    create_group(session, user, hero_level=10)
    deal_damage(session, user, HP_PER_MEMBER)  # добивает единственного участника -> won

    earned = check_and_award_achievements(session, user)
    codes = {a.code for a in earned}
    assert "boss_bronze" in codes


def test_all_personas_stage5_achievement(client, session):
    register_user(client, login="tier5", mail="tier5@example.com")
    user = session.exec(select(User).where(User.login == "tier5")).first()

    # уровень 20 = XP >= 950 (1 + 950//50 = 20) для всех 5 сфер
    for sphere in ("strength", "intellect", "discipline", "health", "charisma"):
        session.add(PointsLog(uid=user.id, points=1000, sphere=sphere, time=_now()))
    session.commit()

    earned = check_and_award_achievements(session, user)
    codes = {a.code for a in earned}
    assert "all_personas_stage5" in codes


def test_tier_achievement_not_awarded_twice(client, session):
    register_user(client, login="tier6", mail="tier6@example.com")
    user = session.exec(select(User).where(User.login == "tier6")).first()
    session.add(PointsLog(uid=user.id, points=500, sphere="strength", time=_now()))
    session.commit()

    first = check_and_award_achievements(session, user)
    second = check_and_award_achievements(session, user)
    first_codes = {a.code for a in first}
    second_codes = {a.code for a in second}
    assert "sphere_bronze" in first_codes
    assert "sphere_bronze" not in second_codes
