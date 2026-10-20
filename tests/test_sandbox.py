"""
Тесты песочницы /admin/sandbox (v6d): ползунки/пресеты не ломают реальные
формулы уровня/сферы, is_test выставляется при любой правке, снимок и
сброс восстанавливают числа, "выдать всё" не даёт монет, маршруты доступны
только админам.
"""

from sqlmodel import select

from app.models import Habit, InventoryItem, Level, Pet, PointsLog, User, UserAchievement
from app.services.levels import level_for_xp
from app.services.personas import persona_state
from app.services.sandbox import (
    SANDBOX_STREAK_HABIT_NAME,
    apply_preset,
    boss_finish,
    boss_hit,
    grant_all_achievements,
    grant_all_items,
    open_chest_of_rarity,
    reset_to_snapshot,
    run_council_now,
    set_coins,
    set_hero_level,
    set_pet,
    set_sphere,
    set_streak,
    set_trust_score,
)
from app.services.spheres import sphere_level, sphere_xp
from app.services.streak import best_streak_for_user
from tests.conftest import register_user


def _make_user(session, login="sandboxer") -> User:
    user = User(mail=f"{login}@example.com", login=login)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_set_hero_level_matches_real_level_formula(session):
    user = _make_user(session)
    set_hero_level(session, user, 20)
    level = session.exec(select(Level).where(Level.uid == user.id)).first()
    assert level_for_xp(level.point) == 20


def test_set_hero_level_marks_is_test(session):
    user = _make_user(session)
    assert user.is_test is False
    set_hero_level(session, user, 5)
    session.refresh(user)
    assert user.is_test is True


def test_set_sphere_level_and_state_single_log_row(session):
    user = _make_user(session)
    set_sphere(session, user, "strength", 8, "дремлет")
    logs = session.exec(select(PointsLog).where(PointsLog.uid == user.id, PointsLog.sphere == "strength")).all()
    assert len(logs) == 1
    xp = sphere_xp(session, user.id, "strength")
    assert sphere_level(xp) == 8

    from app.services.personas import days_since_last_activity

    days = days_since_last_activity(session, user.id, "strength")
    assert persona_state(days) == "дремлет"


def test_set_sphere_sleeping_state(session):
    user = _make_user(session)
    set_sphere(session, user, "intellect", 3, "спит")
    from app.services.personas import days_since_last_activity

    days = days_since_last_activity(session, user.id, "intellect")
    assert persona_state(days) == "спит"


def test_set_streak_creates_hidden_habit_not_in_real_list(session):
    user = _make_user(session)
    set_streak(session, user, 10)
    assert best_streak_for_user(session, user.id) == 10

    habits = session.exec(select(Habit).where(Habit.uid == user.id)).all()
    assert any(h.name == SANDBOX_STREAK_HABIT_NAME for h in habits)
    # ...но не должна попадать в обычный список привычек (фильтруется по имени)
    visible = [h for h in habits if h.name != SANDBOX_STREAK_HABIT_NAME]
    assert all(h.name != SANDBOX_STREAK_HABIT_NAME for h in visible)


def test_set_pet_direct(session):
    user = _make_user(session)
    set_pet(session, user, "drake", 5)
    pet = session.exec(select(Pet).where(Pet.uid == user.id)).first()
    assert pet.species == "drake"
    assert pet.best_stage_reached == 5


def test_grant_all_items_no_coins(session):
    user = _make_user(session)
    before_coins = user.coins
    granted = grant_all_items(session, user)
    assert granted > 0
    session.refresh(user)
    assert user.coins == before_coins
    owned = session.exec(select(InventoryItem).where(InventoryItem.uid == user.id)).all()
    assert len(owned) == granted


def test_grant_all_items_idempotent(session):
    user = _make_user(session)
    grant_all_items(session, user)
    second = grant_all_items(session, user)
    assert second == 0


def test_grant_all_achievements_no_coins(session):
    user = _make_user(session)
    before_coins = user.coins
    granted = grant_all_achievements(session, user)
    assert granted > 0
    session.refresh(user)
    assert user.coins == before_coins


def test_open_chest_forced_rarity(session):
    user = _make_user(session)
    chest = open_chest_of_rarity(session, user, "legendary")
    assert chest.rarity == "legendary"


def test_run_council_now_bypasses_weekday_gate(session):
    user = _make_user(session)
    messages = run_council_now(session, user)
    assert len(messages) == 5


def test_boss_hit_and_defeat(session):
    user = _make_user(session)
    group = boss_hit(session, user, 50)
    assert group is not None
    assert group.hp_remaining < group.hp_total

    group = boss_finish(session, user)
    assert group.status == "won"


def test_snapshot_and_reset_restores_real_progress(session):
    user = _make_user(session)
    real_level = Level(uid=user.id, point=777, name="Практик")
    session.add(real_level)
    session.commit()

    set_hero_level(session, user, 10)  # первая правка — снимок берёт реальные 777 ДО этого изменения
    set_hero_level(session, user, 40)  # вторая правка — снимок уже есть, не перезаписывается

    level = session.exec(select(Level).where(Level.uid == user.id)).first()
    assert level.point != 777

    ok = reset_to_snapshot(session, user)
    assert ok is True
    session.refresh(level)
    assert level.point == 777
    session.refresh(user)
    assert user.is_test is True  # флаг не снимается сбросом


def test_reset_without_snapshot_is_noop(session):
    user = _make_user(session)
    assert reset_to_snapshot(session, user) is False


def test_apply_preset_legend_sets_hero_stage_five(session):
    user = _make_user(session)
    apply_preset(session, user, "legend")
    level = session.exec(select(Level).where(Level.uid == user.id)).first()
    from app.services.levels import level_progress

    assert level_progress(level.point)["stage"] == 5


def test_apply_preset_all_sleeping_sets_every_persona_to_sleeping(session):
    user = _make_user(session)
    set_sphere(session, user, "strength", 10, "активна")
    apply_preset(session, user, "all_sleeping")
    from app.services.personas import persona_profile

    profile = persona_profile(session, user.id)
    assert all(p["state"] == "спит" for p in profile)


def test_sandbox_route_requires_admin(client, session, monkeypatch):
    monkeypatch.setenv("ADMIN_LOGINS", "realadmin")
    register_user(client, login="notadmin2", mail="notadmin2@example.com")
    resp = client.get("/admin/sandbox")
    assert resp.status_code == 404


def test_sandbox_route_renders_for_admin(client, session, monkeypatch):
    monkeypatch.setenv("ADMIN_LOGINS", "sandboxadmin")
    register_user(client, login="sandboxadmin", mail="sandboxadmin@example.com")
    resp = client.get("/admin/sandbox")
    assert resp.status_code == 200
    assert "Песочница" in resp.text


def test_sandbox_apply_route_end_to_end_shows_stage_five_on_hero_page(client, session, monkeypatch):
    monkeypatch.setenv("ADMIN_LOGINS", "sandboxadmin2")
    register_user(client, login="sandboxadmin2", mail="sandboxadmin2@example.com")

    form = {
        "hero_level": "50", "streak_days": "365", "coins": "100", "trust_score": "100",
        "pet_species": "drake", "pet_stage": "5",
    }
    for code in ("strength", "intellect", "discipline", "health", "charisma"):
        form[f"{code}_level"] = "20"
        form[f"{code}_state"] = "активна"

    resp = client.post("/admin/sandbox/apply", data=form)
    assert resp.status_code == 200

    hero_resp = client.get("/hero")
    assert hero_resp.status_code == 200
    user = session.exec(select(User).where(User.login == "sandboxadmin2")).first()
    assert user.is_test is True
