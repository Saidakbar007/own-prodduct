"""Недельная рефлексия (доп. задача, см. app/services/weekly_reflection.py и
docs/decisions/DECISIONS.md → «Этап "Доделай" + guide + wger»): 5 вопросов
кнопками, по одному разу на каждый вопрос в неделе."""

from datetime import date, timedelta

from sqlmodel import select

from app.models import User
from app.newlife.weekly_reflection_bank import load_weekly_reflection
from app.services.weekly_reflection import (
    answered_question_ids_this_week,
    next_question,
    record_answer,
    week_start,
)

THIS_YEAR = date.today().year


def _register_payload(unique: str, **overrides):
    payload = {
        "name": "Рефлексия Тест",
        "birth_year": THIS_YEAR - 25,
        "age_confirm": "1",
        "email": f"wr-{unique}@example.com",
        "login": f"wr-{unique}",
        "password": "s3cret-pass",
        "password_confirm": "s3cret-pass",
        "timezone": "UTC",
    }
    payload.update(overrides)
    return payload


def _register(client, unique):
    client.post("/onboarding/spheres", data={"sphere_ids": ["body"]})
    client.post("/onboarding/sphere-level", data={"option_index": "2"})
    return client.post("/register", data=_register_payload(unique), follow_redirects=True)


def test_week_start_is_monday_of_the_week():
    wednesday = date(2026, 11, 11)  # среда
    assert week_start(wednesday) == date(2026, 11, 9)  # понедельник той же недели


def test_bank_has_exactly_five_bilingual_questions():
    questions = load_weekly_reflection()
    assert len(questions) == 5
    for q in questions:
        assert q.text.ru.strip() and q.text.uz.strip()
        for option in q.options:
            assert option.ru.strip() and option.uz.strip()


def test_today_never_shows_the_weekly_reflection_card(client, unique):
    """NEWLIFE_2_0.md Этап 1 п.5: «На Сегодня снова опрос» — убрать.
    Единственный допустимый опрос на «Сегодня» — «вопрос дня»
    (app/services/day_questions.py); недельная рефлексия была вторым
    опросом на этом же экране и убрана оттуда (функции/данные остаются,
    карточка на «Сегодня» не рисуется)."""
    _register(client, unique)
    resp = client.get("/today")
    assert resp.status_code == 200
    assert "Недельная рефлексия" not in resp.text


def test_answers_do_not_carry_over_to_next_week(db_session):
    user = User(
        name="X", login="wr-nextweek", email="wr-nextweek@example.com",
        password_hash="x", timezone="UTC", birth_year=THIS_YEAR - 25,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    this_monday = date(2026, 11, 9)
    next_monday = this_monday + timedelta(days=7)
    first_question = load_weekly_reflection()[0]
    record_answer(db_session, user.id, first_question.id, 0, this_monday)

    assert next_question(db_session, user.id, this_monday).id != first_question.id
    assert next_question(db_session, user.id, next_monday).id == first_question.id
