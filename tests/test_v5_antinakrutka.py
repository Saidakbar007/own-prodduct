"""
Тесты антинакрутки очков (v5, пункт 4): каталог типовых привычек,
сложность своей привычки считает сервер (не выше расчётной), дневной
лимит XP на сферу, перекалибровка после 30 дней подряд 100%.
"""

from datetime import timedelta

from sqlmodel import select

from app.models import Habit, HabitHistory, Level, PointsLog, User
from app.routers.habits import _now
from app.services.catalog import CATALOG, find_by_code
from app.services.difficulty import calculate_difficulty_by_rules, clamp_difficulty, step_down
from app.services.points import HABIT_DIFFICULTY_POINTS
from app.services.recalibration import maybe_recalibrate
from app.services.spheres import DAILY_SPHERE_CAP, log_sphere_xp
from tests.conftest import register_user


def test_catalog_has_at_least_30_items_with_sphere_and_difficulty():
    assert len(CATALOG) >= 30
    for item in CATALOG:
        assert item["sphere"]
        assert item["difficulty"] in ("easy", "medium", "hard")
        assert find_by_code(item["code"]) == item


def test_create_habit_from_catalog_ignores_client_difficulty(client, session):
    register_user(client, login="kate", mail="kate@example.com")
    water = find_by_code("water")

    resp = client.post(
        "/habits",
        data={"source": "catalog", "catalog_code": "water", "difficulty": "hard"},  # клиент пытается завысить
    )
    assert resp.status_code == 200

    user = session.exec(select(User).where(User.login == "kate")).first()
    habit = session.exec(select(Habit).where(Habit.uid == user.id)).first()
    assert habit.name == water["name"]
    assert habit.sphere == water["sphere"]
    assert habit.point == HABIT_DIFFICULTY_POINTS[water["difficulty"]]


def test_custom_habit_requires_valid_sphere(client, session):
    register_user(client, login="liu2", mail="liu2@example.com")
    resp = client.post("/habits", data={"source": "custom", "name": "Своя привычка"})
    assert resp.status_code == 400

    resp2 = client.post("/habits", data={"source": "custom", "name": "Своя привычка", "sphere": "not-a-sphere"})
    assert resp2.status_code == 400

    habits = session.exec(select(Habit)).all()
    assert habits == []


def test_custom_habit_difficulty_cannot_exceed_server_calculation(client, session):
    register_user(client, login="miro", mail="miro@example.com")
    # "Бег" без цифр/ключевых слов — сервер оценит как medium, даже если
    # клиент заявил hard
    resp = client.post(
        "/habits",
        data={"source": "custom", "name": "Бег", "sphere": "strength", "difficulty": "hard"},
    )
    assert resp.status_code == 200

    user = session.exec(select(User).where(User.login == "miro")).first()
    habit = session.exec(select(Habit).where(Habit.uid == user.id)).first()
    assert habit.point == HABIT_DIFFICULTY_POINTS["medium"]  # не "hard" (20)


def test_custom_habit_can_claim_lower_than_calculated(client, session):
    register_user(client, login="nina2", mail="nina2@example.com")
    # "Марафон" сервер оценит как hard, но клиент сам занижает до easy — это разрешено
    resp = client.post(
        "/habits",
        data={"source": "custom", "name": "Марафон", "sphere": "strength", "difficulty": "easy"},
    )
    assert resp.status_code == 200

    user = session.exec(select(User).where(User.login == "nina2")).first()
    habit = session.exec(select(Habit).where(Habit.uid == user.id)).first()
    assert habit.point == HABIT_DIFFICULTY_POINTS["easy"]


def test_difficulty_rules_detect_numeric_targets():
    assert calculate_difficulty_by_rules("Читать 5 минут") == "easy"
    assert calculate_difficulty_by_rules("Читать 20 минут") == "medium"
    assert calculate_difficulty_by_rules("Читать 60 минут") == "hard"
    assert calculate_difficulty_by_rules("Пробежать марафон") == "hard"
    assert calculate_difficulty_by_rules("Выпить хотя бы стакан воды") == "easy"


def test_clamp_and_step_down_never_exceed_input():
    assert clamp_difficulty("hard", "easy") == "easy"
    assert clamp_difficulty("easy", "hard") == "easy"
    assert clamp_difficulty("medium", "medium") == "medium"
    assert step_down("hard") == "medium"
    assert step_down("medium") == "easy"
    assert step_down("easy") == "easy"


def test_daily_sphere_xp_cap_limits_awarded_amount(client, session):
    register_user(client, login="omar2", mail="omar2@example.com")
    user = session.exec(select(User).where(User.login == "omar2")).first()

    first = log_sphere_xp(session, user.id, "strength", DAILY_SPHERE_CAP - 10)
    assert first == DAILY_SPHERE_CAP - 10

    second = log_sphere_xp(session, user.id, "strength", 50)  # запросили 50, осталось только 10
    assert second == 10

    third = log_sphere_xp(session, user.id, "strength", 50)  # лимит на сегодня исчерпан
    assert third == 0

    logs = session.exec(select(PointsLog).where(PointsLog.uid == user.id, PointsLog.sphere == "strength")).all()
    assert sum(log.points for log in logs) == DAILY_SPHERE_CAP


def test_daily_sphere_cap_is_per_sphere_not_global(client, session):
    register_user(client, login="priya2", mail="priya2@example.com")
    user = session.exec(select(User).where(User.login == "priya2")).first()

    log_sphere_xp(session, user.id, "strength", DAILY_SPHERE_CAP)
    # другая сфера в тот же день — свой собственный лимит, не затронут
    awarded = log_sphere_xp(session, user.id, "intellect", 50)
    assert awarded == 50


def test_recalibration_lowers_difficulty_after_30_perfect_days(client, session):
    register_user(client, login="quen", mail="quen@example.com")
    client.post("/habits", data={"source": "custom", "name": "Марафон", "sphere": "strength", "difficulty": "hard"})
    user = session.exec(select(User).where(User.login == "quen")).first()
    habit = session.exec(select(Habit).where(Habit.uid == user.id)).first()
    assert habit.point == HABIT_DIFFICULTY_POINTS["hard"]

    for days_ago in range(29, -1, -1):
        session.add(HabitHistory(h_id=habit.id, time=_now() - timedelta(days=days_ago), kind="done"))
    session.commit()

    new_difficulty = maybe_recalibrate(session, habit)
    session.refresh(habit)
    assert new_difficulty == "medium"
    assert habit.point == HABIT_DIFFICULTY_POINTS["medium"]
    assert habit.last_recalibration is not None


def test_recalibration_respects_30_day_cooldown(client, session):
    register_user(client, login="rosa2", mail="rosa2@example.com")
    client.post("/habits", data={"source": "custom", "name": "Марафон", "sphere": "strength", "difficulty": "hard"})
    user = session.exec(select(User).where(User.login == "rosa2")).first()
    habit = session.exec(select(Habit).where(Habit.uid == user.id)).first()

    for days_ago in range(29, -1, -1):
        session.add(HabitHistory(h_id=habit.id, time=_now() - timedelta(days=days_ago), kind="done"))
    session.commit()

    first = maybe_recalibrate(session, habit)
    assert first == "medium"

    second = maybe_recalibrate(session, habit)  # тот же день — повторно не калибруем
    assert second is None
