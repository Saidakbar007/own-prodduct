"""«Я» (§12, §14): колесо жизни, обязательные дела, Методы NewLife,
Откуда эти нормы, О NewLife."""

from datetime import date

from sqlmodel import select

from app.models import SphereState, User

THIS_YEAR = date.today().year


def _register(client, unique, spheres=("body", "energy")):
    client.post("/onboarding/spheres", data={"sphere_ids": list(spheres)})
    for _ in spheres:
        client.post("/onboarding/sphere-level", data={"option_index": "2"})
    client.post("/onboarding/goal/skip")
    client.post("/onboarding/mode", data={"wake_time": "07:00", "sleep_time": "23:00"})
    client.post("/onboarding/commitments", data={"action": "next"})
    client.post("/onboarding/daily-minutes", data={"daily_minutes": "30"})
    client.post("/onboarding/chronotype", data={"chronotype": "morning"})
    client.post("/onboarding/constraints", data={})
    client.post("/onboarding/woop", data={})
    client.post(
        "/register",
        data={
            "name": "Me Routes", "birth_year": str(THIS_YEAR - 25), "age_confirm": "1",
            "email": f"me-{unique}@example.com", "login": f"me-{unique}",
            "password": "s3cret-pass", "password_confirm": "s3cret-pass", "timezone": "UTC",
        },
    )


def test_profile_shows_life_wheel_mini(client, unique):
    _register(client, unique)
    resp = client.get("/profile")
    assert resp.status_code == 200
    assert "Колесо жизни" in resp.text
    assert "Тело" in resp.text


def test_wheel_page_lists_all_spheres(client, unique):
    _register(client, unique)
    resp = client.get("/profile/wheel")
    assert resp.status_code == 200
    assert "Тело" in resp.text
    assert "Финансы" in resp.text  # не выбранная сфера, но показана с "скоро"


def test_wheel_level_adjustment_persists(client, unique, db_session):
    _register(client, unique)
    user = db_session.exec(select(User).where(User.login == f"me-{unique}")).first()
    before = db_session.exec(
        select(SphereState).where(SphereState.uid == user.id, SphereState.sphere_id == "body")
    ).first()
    start_level = before.level

    client.post("/profile/wheel/body/level", data={"delta": "1"})
    db_session.refresh(before)
    assert before.level == min(10, start_level + 1)


def test_wheel_level_clamped_to_ten(client, unique, db_session):
    _register(client, unique)
    user = db_session.exec(select(User).where(User.login == f"me-{unique}")).first()
    state = db_session.exec(
        select(SphereState).where(SphereState.uid == user.id, SphereState.sphere_id == "body")
    ).first()
    for _ in range(15):
        client.post("/profile/wheel/body/level", data={"delta": "1"})
    db_session.refresh(state)
    assert state.level == 10


def test_methods_page_lists_all_twelve(client, unique):
    _register(client, unique)
    resp = client.get("/methods")
    assert resp.status_code == 200
    assert "Режим восстановления" in resp.text
    assert "WOOP" in resp.text


def test_sources_page_renders(client, unique):
    _register(client, unique)
    resp = client.get("/sources")
    assert resp.status_code == 200
    assert "NHS" in resp.text or "ACSM" in resp.text


def test_about_page_renders(client, unique):
    _register(client, unique)
    resp = client.get("/about")
    assert resp.status_code == 200
    assert "NewLife" in resp.text


def test_help_page_always_shows_103_and_112(client, unique, monkeypatch):
    monkeypatch.delenv("HELPLINE_UZ", raising=False)
    _register(client, unique)
    resp = client.get("/help")
    assert resp.status_code == 200
    assert "103" in resp.text
    assert "112" in resp.text


def test_help_page_shows_configured_psych_helpline(client, unique, monkeypatch):
    monkeypatch.setenv("HELPLINE_UZ", "+998712000000")
    _register(client, unique)
    resp = client.get("/help")
    assert resp.status_code == 200
    assert "+998712000000" in resp.text


def test_profile_commitments_page_add_and_remove(client, unique, db_session):
    _register(client, unique)
    client.post(
        "/week/commitments/add",
        data={"title": "Пары", "category": "study", "weekdays": ["1", "3"], "start_time": "09:00", "end_time": "14:00"},
    )
    page = client.get("/profile/commitments")
    assert "Пары" in page.text

    from app.models import Commitment

    c = db_session.exec(select(Commitment).where(Commitment.title == "Пары")).first()
    client.post(f"/profile/commitments/{c.id}/remove")
    page2 = client.get("/profile/commitments")
    assert "Пары" not in page2.text
