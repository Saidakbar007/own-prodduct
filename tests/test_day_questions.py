"""Вопрос дня (PRD 1.0 F7): первые 7 дней после регистрации — по одному
вопросу в день на "Сегодня" из активных сфер."""

from datetime import date, timedelta

from sqlmodel import select

from app.models import DayQuestionAnswer, Profile, User
from app.services.day_questions import record_answer, todays_question

THIS_YEAR = date.today().year


def _register_payload(unique: str, **overrides):
    payload = {
        "name": "Вопрос Дня Тест",
        "birth_year": THIS_YEAR - 25,
        "age_confirm": "1",
        "email": f"dq-{unique}@example.com",
        "login": f"dq-{unique}",
        "password": "s3cret-pass",
        "password_confirm": "s3cret-pass",
        "timezone": "UTC",
    }
    payload.update(overrides)
    return payload


def _register_with_spheres(client, unique, spheres=("body", "energy")):
    client.post("/onboarding/spheres", data={"sphere_ids": list(spheres)})
    for _ in spheres:
        client.post("/onboarding/sphere-level", data={"option_index": "2"})
    return client.post("/register", data=_register_payload(unique), follow_redirects=True)


def test_today_shows_a_question_on_day_one(client, unique, db_session):
    _register_with_spheres(client, unique)
    resp = client.get("/today")
    assert resp.status_code == 200
    assert "Вопрос дня" in resp.text


def test_submitting_answer_records_it_and_clears_todays_card(client, unique, db_session):
    _register_with_spheres(client, unique)
    resp = client.get("/today")
    # body — первая выбранная сфера, её первый вопрос должен быть на экране
    assert "Сколько стаканов воды" in resp.text

    client.post("/today/question", data={"question_id": "body_water_today", "option_index": "1"})

    user = db_session.exec(select(User).where(User.login == f"dq-{unique}")).first()
    answer = db_session.exec(select(DayQuestionAnswer).where(DayQuestionAnswer.uid == user.id)).first()
    assert answer is not None
    assert answer.question_id == "body_water_today"
    assert answer.option_index == 1
    assert answer.option_text == "3–4"

    # второй вопрос в тот же день не должен появиться (один в день)
    resp2 = client.get("/today")
    assert "Вопрос дня" not in resp2.text


def test_todays_question_none_outside_first_week(db_session, client, unique):
    _register_with_spheres(client, unique)
    user = db_session.exec(select(User).where(User.login == f"dq-{unique}")).first()
    profile = db_session.exec(select(Profile).where(Profile.uid == user.id)).first()

    assert todays_question(db_session, user.id, profile, date.today()) is not None

    far_future = date.today() + timedelta(days=30)
    assert todays_question(db_session, user.id, profile, far_future) is None


def test_record_answer_rejects_unknown_question_or_bad_option(db_session, client, unique):
    _register_with_spheres(client, unique)
    user = db_session.exec(select(User).where(User.login == f"dq-{unique}")).first()
    today = date.today()

    assert record_answer(db_session, user.id, "does-not-exist", 0, today) is None
    assert record_answer(db_session, user.id, "body_water_today", 99, today) is None
    assert record_answer(db_session, user.id, "body_water_today", 0, today) is not None


def test_profile_shows_answered_day_question(client, unique, db_session):
    _register_with_spheres(client, unique)
    client.post("/today/question", data={"question_id": "body_water_today", "option_index": "2"})

    resp = client.get("/profile")
    assert resp.status_code == 200
    assert "Сколько стаканов воды" in resp.text
    assert "5–6" in resp.text


def test_questions_admin_accessible_and_lists_spheres(client, monkeypatch, unique):
    login = f"admin-q-{unique}"
    monkeypatch.setenv("ADMIN_LOGINS", login)
    client.post(
        "/register",
        data={
            "name": "Admin Q", "birth_year": str(THIS_YEAR - 25), "age_confirm": "1",
            "email": f"{login}@example.com", "login": login,
            "password": "s3cret-pass", "password_confirm": "s3cret-pass", "timezone": "UTC",
        },
    )
    resp = client.get("/admin/questions")
    assert resp.status_code == 200
    assert "body_water_today" in resp.text
