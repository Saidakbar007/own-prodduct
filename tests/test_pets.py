"""
Тесты питомца героя (v6b): яйцо с 3-го уровня, выбор вида, стадии по серии,
стадия не откатывается, настроение, защита заморозкой.
"""

from datetime import timedelta

from sqlmodel import select

from app.models import Habit, HabitHistory, Pet, User
from app.routers.habits import _now
from app.services.levels import xp_for_level
from app.services.pets import (
    HATCH_MIN_HERO_LEVEL,
    can_hatch,
    get_or_create_pet,
    hatch_pet,
    pet_mood,
    pet_profile,
    stage_for_streak,
    sync_pet_stage,
)
from tests.conftest import register_user


def test_stage_for_streak_thresholds():
    assert stage_for_streak(0) == 1
    assert stage_for_streak(6) == 1
    assert stage_for_streak(7) == 2
    assert stage_for_streak(29) == 2
    assert stage_for_streak(30) == 3
    assert stage_for_streak(99) == 3
    assert stage_for_streak(100) == 4
    assert stage_for_streak(364) == 4
    assert stage_for_streak(365) == 5
    assert stage_for_streak(10000) == 5


def test_can_hatch_requires_level_3():
    assert can_hatch(1) is False
    assert can_hatch(2) is False
    assert can_hatch(3) is True
    assert can_hatch(10) is True


def test_hatch_blocked_below_level_3(client, session):
    register_user(client, login="pet1", mail="pet1@example.com")
    user = session.exec(select(User).where(User.login == "pet1")).first()

    ok, message = hatch_pet(session, user, hero_level=2, species="fox")
    assert ok is False
    pet = get_or_create_pet(session, user.id)
    assert pet.species is None


def test_hatch_succeeds_at_level_3_and_only_once(client, session):
    register_user(client, login="pet2", mail="pet2@example.com")
    user = session.exec(select(User).where(User.login == "pet2")).first()

    ok, message = hatch_pet(session, user, hero_level=3, species="owl")
    assert ok is True
    pet = get_or_create_pet(session, user.id)
    assert pet.species == "owl"
    assert pet.hatched_at is not None

    ok2, message2 = hatch_pet(session, user, hero_level=5, species="drake")
    assert ok2 is False
    session.refresh(pet)
    assert pet.species == "owl"  # не переписался


def test_hatch_rejects_unknown_species(client, session):
    register_user(client, login="pet3", mail="pet3@example.com")
    user = session.exec(select(User).where(User.login == "pet3")).first()

    ok, message = hatch_pet(session, user, hero_level=5, species="unicorn")
    assert ok is False


def test_pet_stage_does_not_roll_back(client, session):
    register_user(client, login="pet4", mail="pet4@example.com")
    user = session.exec(select(User).where(User.login == "pet4")).first()
    hatch_pet(session, user, hero_level=3, species="fox")

    pet = sync_pet_stage(session, user, current_streak=30)
    assert pet.best_stage_reached == 3

    pet_after_drop = sync_pet_stage(session, user, current_streak=0)
    assert pet_after_drop.best_stage_reached == 3  # не откатилась


def test_pet_mood_sad_only_after_reaching_real_stage(client, session):
    register_user(client, login="pet5", mail="pet5@example.com")
    user = session.exec(select(User).where(User.login == "pet5")).first()
    hatch_pet(session, user, hero_level=3, species="fox")

    fresh_pet = get_or_create_pet(session, user.id)
    assert pet_mood(fresh_pet, current_streak=0) == "весело"  # ещё не было нормальной серии

    sync_pet_stage(session, user, current_streak=10)
    pet = get_or_create_pet(session, user.id)
    assert pet_mood(pet, current_streak=0) == "грустно"
    assert pet_mood(pet, current_streak=5) == "весело"


def test_pet_profile_shows_egg_before_hatch(client, session):
    register_user(client, login="pet6", mail="pet6@example.com")
    user = session.exec(select(User).where(User.login == "pet6")).first()

    profile = pet_profile(session, user, hero_level=3, current_streak=0)
    assert profile["egg"] is True
    assert profile["can_hatch"] is True
    assert profile["species"] is None


def test_pet_profile_locked_before_level_3(client, session):
    register_user(client, login="pet7", mail="pet7@example.com")
    user = session.exec(select(User).where(User.login == "pet7")).first()

    profile = pet_profile(session, user, hero_level=1, current_streak=0)
    assert profile["can_hatch"] is False


def test_hatch_route_via_http(client, session):
    register_user(client, login="pet8", mail="pet8@example.com")
    user = session.exec(select(User).where(User.login == "pet8")).first()

    from app.services.points import award_points

    award_points(session, user, xp_for_level(1) + xp_for_level(2))  # поднимает до ур.3

    resp = client.post("/pet/hatch", data={"species": "drake"})
    assert resp.status_code == 200
    assert "Дракончик" in resp.text

    pet = session.exec(select(Pet).where(Pet.uid == user.id)).first()
    assert pet.species == "drake"


def test_freeze_protects_pet_from_sadness(client, session):
    """
    Заморозка защищает серию (как в calculate_streak_with_freeze) — значит
    защищает и питомца от "грусти", без отдельной логики (см. DECISIONS.md, п.8).
    """
    register_user(client, login="pet9", mail="pet9@example.com")
    client.post("/habits", data={"source": "custom", "name": "Бег", "sphere": "strength"})
    user = session.exec(select(User).where(User.login == "pet9")).first()
    habit = session.exec(select(Habit).where(Habit.uid == user.id)).first()
    hatch_pet(session, user, hero_level=3, species="fox")

    today = _now()
    for days_ago in range(10, -1, -1):
        if days_ago == 5:
            continue  # один пропущенный день без отметки — заморозка должна его прикрыть
        session.add(HabitHistory(h_id=habit.id, time=today - timedelta(days=days_ago), kind="done"))
    session.commit()

    from app.routers.habits import best_streak_with_freeze_for_user

    streak = best_streak_with_freeze_for_user(session, user)
    assert streak > 0  # серия не обрушилась из-за одного пропуска — заморозка спасла

    pet = sync_pet_stage(session, user, streak)
    assert pet_mood(pet, streak) == "весело"
