"""Полный мастер NewLife v8 (§5): философия -> сферы -> уровень -> цель ->
режим -> обязательные дела -> время/силы/ограничения -> WOOP -> раскрытие ->
регистрация. Проверяем, что Profile/SphereState/Commitment/Goal реально
попадают в БД с правильными значениями, а не только статус-коды 200/303."""

from datetime import date

from sqlmodel import select

from app.models import Commitment, Goal, Profile, Season, SphereState

THIS_YEAR = date.today().year


def _register_payload(unique: str, **overrides):
    payload = {
        "name": "НьюЛайф Тестов",
        "birth_year": THIS_YEAR - 25,
        "age_confirm": "1",
        "email": f"nl-{unique}@example.com",
        "login": f"nl-{unique}",
        "password": "s3cret-pass",
        "password_confirm": "s3cret-pass",
        "timezone": "UTC",
    }
    payload.update(overrides)
    return payload


def test_full_wizard_creates_profile_sphere_state_commitment_and_goal(client, unique, db_session):
    assert client.get("/onboarding").status_code == 200

    client.post("/onboarding/spheres", data={"sphere_ids": ["body", "energy"]})

    # Экран 3: уровень по каждой выбранной сфере (body, затем energy).
    r1 = client.get("/onboarding/sphere-level")
    assert r1.status_code == 200
    client.post("/onboarding/sphere-level", data={"option_index": "2"})
    r2 = client.get("/onboarding/sphere-level")
    assert r2.status_code == 200
    client.post("/onboarding/sphere-level", data={"option_index": "1"})

    # После цикла уровней -> каталог целей (body выбран -> полноценный каталог)
    goal_page = client.get("/onboarding/sphere-level", follow_redirects=True)
    assert goal_page.status_code == 200

    client.post("/onboarding/goal", data={"template_id": "pushups_50"})
    client.post("/onboarding/baseline", data={"value": "5"})
    client.post("/onboarding/schedule", data={"length_days": "30"})

    client.post("/onboarding/mode", data={"wake_time": "06:30", "sleep_time": "22:30"})
    client.post(
        "/onboarding/commitments",
        data={
            "title": "Учёба",
            "category": "study",
            "weekdays": ["1", "2", "3", "4", "5"],
            "start_time": "09:00",
            "end_time": "17:00",
            "action": "add",
        },
    )
    client.post("/onboarding/commitments", data={"action": "next", "commute_minutes": "30"})
    client.post("/onboarding/daily-minutes", data={"daily_minutes": "30"})
    client.post("/onboarding/chronotype", data={"chronotype": "morning"})
    client.post("/onboarding/constraints", data={"constraints": ["no_gym", "low_budget"]})
    client.post("/onboarding/woop/obstacle", data={"main_obstacle": "forget"})
    client.post("/onboarding/woop", data={"plan": "anchor"})

    trailer = client.get("/onboarding/trailer")
    assert trailer.status_code == 200
    assert "отжиманий" in trailer.text  # есть карточка цели
    assert "Тело" in trailer.text  # есть колесо жизни с выбранными сферами

    reg = client.post("/register", data=_register_payload(unique), follow_redirects=True)
    assert reg.status_code == 200
    assert "День 1" in reg.text

    # --- проверяем реальное состояние в БД, не только HTTP-коды ---
    season = db_session.exec(select(Season).order_by(Season.id.desc())).first()
    assert season.template_id == "pushups_50"
    assert season.goal_id is not None

    goal = db_session.get(Goal, season.goal_id)
    assert goal.sphere_id == "body"
    assert goal.template_id == "pushups_50"
    assert goal.metric_key == "max_reps"

    profile = db_session.exec(select(Profile).where(Profile.uid == season.uid)).first()
    assert profile is not None
    assert profile.wake_time == "06:30"
    assert profile.sleep_time == "22:30"
    assert profile.daily_minutes == 30
    assert profile.chronotype == "morning"
    assert profile.main_obstacle == "forget"
    assert profile.onboarding_done_at is not None
    import json
    assert set(json.loads(profile.constraints_json)) == {"no_gym", "low_budget"}

    sphere_states = db_session.exec(select(SphereState).where(SphereState.uid == season.uid)).all()
    sphere_ids = {s.sphere_id for s in sphere_states}
    assert sphere_ids == {"body", "energy"}
    body_state = next(s for s in sphere_states if s.sphere_id == "body")
    assert 1 <= body_state.level <= 10
    assert body_state.active is True

    commitments = db_session.exec(select(Commitment).where(Commitment.uid == season.uid)).all()
    assert len(commitments) == 1
    assert commitments[0].title == "Учёба"
    assert commitments[0].category == "study"
    assert json.loads(commitments[0].weekdays_json) == [1, 2, 3, 4, 5]


def test_spheres_skip_defaults_to_body(client):
    client.get("/onboarding")
    resp = client.post("/onboarding/spheres", data={}, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/onboarding/sphere-level"


def test_returning_user_with_completed_profile_skips_wizard(client, unique, db_session):
    """После первого прохождения /onboarding ведёт сразу в каталог целей."""
    client.post("/onboarding/spheres", data={"sphere_ids": ["body"]})
    client.post("/onboarding/sphere-level", data={"option_index": "1"})
    client.post("/onboarding/goal", data={"template_id": "run_5k"})
    client.post("/onboarding/baseline", data={"value": "5"})
    client.post("/onboarding/schedule", data={"length_days": "60"})
    client.post("/onboarding/mode", data={})
    client.post("/onboarding/commitments", data={"action": "next"})
    client.post("/onboarding/daily-minutes", data={"daily_minutes": "30"})
    client.post("/onboarding/chronotype", data={"chronotype": "varies"})
    client.post("/onboarding/constraints", data={})
    client.post("/onboarding/woop", data={})
    client.post("/register", data=_register_payload(unique))

    resp = client.get("/onboarding", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/onboarding/goal"
