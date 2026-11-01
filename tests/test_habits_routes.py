"""HTTP-роуты /habits (§10, §14) — добавление из каталога/своя, лог,
плохие привычки: полный путь через клиента, не только сервисный слой."""

from datetime import date

from sqlmodel import select

from app.models import BadHabit, Habit, User

THIS_YEAR = date.today().year


def _register(client, unique):
    client.post("/onboarding/spheres", data={"sphere_ids": ["body"]})
    client.post("/onboarding/sphere-level", data={"option_index": "1"})
    client.post("/onboarding/goal/skip")
    client.post("/onboarding/mode", data={})
    client.post("/onboarding/commitments", data={"action": "next"})
    client.post("/onboarding/daily-minutes", data={"daily_minutes": "30"})
    client.post("/onboarding/chronotype", data={"chronotype": "varies"})
    client.post("/onboarding/constraints", data={})
    client.post("/onboarding/woop", data={})
    client.post(
        "/register",
        data={
            "name": "Habit Routes", "birth_year": str(THIS_YEAR - 25), "age_confirm": "1",
            "email": f"hr-{unique}@example.com", "login": f"hr-{unique}",
            "password": "s3cret-pass", "password_confirm": "s3cret-pass", "timezone": "UTC",
        },
    )


def test_habits_page_requires_login(client):
    resp = client.get("/habits", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


def test_add_habit_from_catalog_and_log_done(client, unique, db_session):
    _register(client, unique)

    resp = client.get("/habits/add")
    assert resp.status_code == 200
    assert "Медитация" in resp.text

    client.post("/habits/add", data={"catalog_id": "meditation", "time_pref": "morning"})
    habit = db_session.exec(select(Habit).where(Habit.catalog_id == "meditation")).first()
    assert habit is not None
    assert habit.title == "Медитация"

    page = client.get("/habits")
    assert "Медитация" in page.text

    done = client.post(f"/habits/{habit.id}/log", data={"status": "done"}, follow_redirects=True)
    assert done.status_code == 200
    assert "Сделано" in done.text


def test_add_custom_habit(client, unique, db_session):
    _register(client, unique)
    client.post("/habits/add", data={"custom_title": "Своя привычка дня"})
    habit = db_session.exec(select(Habit).where(Habit.title == "Своя привычка дня")).first()
    assert habit is not None
    assert habit.catalog_id is None
    assert habit.minimal_version  # правило двух минут — всегда есть минимальная версия


def test_add_bad_habit_from_catalog_and_log_slip(client, unique, db_session):
    _register(client, unique)
    user = db_session.exec(select(User).where(User.login == f"hr-{unique}")).first()

    resp = client.get("/habits/bad/add")
    assert resp.status_code == 200
    assert "скролл" in resp.text.lower() or "Скролл" in resp.text

    client.post("/habits/bad/add", data={"catalog_id": "social_media_scroll", "baseline_per_day": "60"})
    bad_habit = db_session.exec(
        select(BadHabit).where(BadHabit.catalog_id == "social_media_scroll", BadHabit.uid == user.id)
    ).first()
    assert bad_habit is not None
    assert bad_habit.unit == "minutes"
    assert bad_habit.target_per_day == 51.0  # 60 * 0.85

    slip = client.post(f"/habits/bad/{bad_habit.id}/slip", data={"trigger_id": "boredom"}, follow_redirects=True)
    assert slip.status_code == 200


def test_deactivate_habit_removes_it_from_list(client, unique, db_session):
    _register(client, unique)
    client.post("/habits/add", data={"custom_title": "Временная привычка"})
    habit = db_session.exec(select(Habit).where(Habit.title == "Временная привычка")).first()

    client.post(f"/habits/{habit.id}/deactivate")
    page = client.get("/habits")
    assert "Временная привычка" not in page.text
