"""Типы ввода метрик (PRD 1.0 F3) и таймер фокуса (F4): виджет на /measure по
metric.kind из каталога, округление через app.newlife.rounding, таймер
фокуса пишет логированные минуты в SeasonDay и предзаполняет замер."""

from datetime import date, timedelta

from sqlmodel import select

from app.models import Measurement, Season, SeasonDay
from app.newlife.goal_catalog import goal_meta
from app.services.seasons import goal_metric_for_season, sum_logged_minutes_since_last_measure

THIS_YEAR = date.today().year


def _register_payload(unique: str, **overrides):
    payload = {
        "name": "Метрики Тест",
        "birth_year": THIS_YEAR - 25,
        "age_confirm": "1",
        "email": f"metric-{unique}@example.com",
        "login": f"metric-{unique}",
        "password": "s3cret-pass",
        "password_confirm": "s3cret-pass",
        "timezone": "UTC",
    }
    payload.update(overrides)
    return payload


def _onboard_and_register(client, unique, template_id, baseline_value, length_days=30, suffix=""):
    client.post("/onboarding/goal", data={"template_id": template_id})
    client.post("/onboarding/baseline", data={"value": str(baseline_value)})
    client.post("/onboarding/schedule", data={"length_days": str(length_days)})
    client.get("/onboarding/trailer")
    login = f"metric-{unique}{suffix}"
    resp = client.post(
        "/register",
        data=_register_payload(unique, login=login, email=f"{login}@example.com"),
        follow_redirects=True,
    )
    assert resp.status_code == 200
    return resp


# --------------------------------------------------------- goal_metric_for_season

def test_goal_metric_for_season_counter_kind(client, unique, db_session):
    _onboard_and_register(client, unique, "sitting_breaks", 5)
    season = db_session.exec(select(Season).order_by(Season.id.desc())).first()
    metric = goal_metric_for_season(season)
    assert metric is not None
    assert metric.kind == "counter"
    entry = goal_meta("sitting_breaks")
    assert metric.unit == entry.metric.unit


# --------------------------------------------------------------- /measure widgets

def test_measure_form_renders_counter_widget_with_plus_minus_buttons(client, unique):
    _onboard_and_register(client, unique, "sitting_breaks", 5)
    resp = client.get("/measure")
    assert resp.status_code == 200
    assert 'id="value"' in resp.text
    assert "+" in resp.text and "−" in resp.text


def test_measure_form_renders_percent_slider(client, unique):
    _onboard_and_register(client, unique, "online_course", 10)
    resp = client.get("/measure")
    assert resp.status_code == 200
    assert 'type="range"' in resp.text
    assert 'max="100"' in resp.text


def test_measure_submit_rounds_counter_value_to_metric_step(client, unique, db_session):
    _onboard_and_register(client, unique, "sitting_breaks", 5)
    # sitting_breaks: metric.rounding == 1 -> дробное значение округляется до целого
    resp = client.post("/measure", data={"value": "6.7"}, follow_redirects=True)
    assert resp.status_code == 200
    measurement = db_session.exec(select(Measurement).order_by(Measurement.id.desc())).first()
    assert measurement.value == 7.0


# ------------------------------------------------------------------- /focus

def test_focus_redirects_away_for_non_timer_goal(client, unique):
    _onboard_and_register(client, unique, "sitting_breaks", 5)
    resp = client.get("/focus", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert resp.headers["location"] == "/today"


def _force_today_as_train_day(db_session, season) -> SeasonDay:
    """День 1 — всегда calendar_date == "сегодня" (сезон стартует в день
    создания, без ожидания понедельника). Он создаётся как kind="measure"
    (точка старта), но уже существует с правильной датой — проще и надёжнее
    форсировать его в "train" на месте, чем двигать season.start_date:
    дни 1..N уже построены скользящим окном при создании сезона с ИСХОДНЫМИ
    датами, и смена start_date задним числом их не переносит."""
    day = db_session.exec(
        select(SeasonDay).where(SeasonDay.season_id == season.id, SeasonDay.day_number == 1)
    ).first()
    assert day is not None
    day.kind = "train"
    day.status = "planned"
    db_session.add(day)
    db_session.commit()
    db_session.refresh(day)
    return day


def test_focus_picker_shown_for_timer_goal_on_a_train_day(client, unique, db_session):
    _onboard_and_register(client, unique, "deep_focus", 60, length_days=60)
    season = db_session.exec(select(Season).order_by(Season.id.desc())).first()
    _force_today_as_train_day(db_session, season)

    resp = client.get("/focus")
    assert resp.status_code == 200
    assert "мин" in resp.text
    assert "breathing-technique-btn" not in resp.text


def test_focus_shows_breathing_technique_picker_for_breathing_goal(client, unique, db_session):
    """Доп. задача (DECISIONS.md → guide/wger): дыхательный таймер с
    анимацией (4-6 / циклический вздох) — только для breathing_practice,
    остальные timer-цели не получают эту разметку (is_breathing=False)."""
    _onboard_and_register(client, unique, "breathing_practice", 5, length_days=30)
    season = db_session.exec(select(Season).order_by(Season.id.desc())).first()
    _force_today_as_train_day(db_session, season)

    resp = client.get("/focus")
    assert resp.status_code == 200
    assert "breathing-technique-btn" in resp.text
    assert "breathing_animation.js" in resp.text


def test_focus_complete_marks_day_done_and_logs_minutes(client, unique, db_session):
    _onboard_and_register(client, unique, "deep_focus", 60, length_days=60)
    season = db_session.exec(select(Season).order_by(Season.id.desc())).first()
    day = _force_today_as_train_day(db_session, season)

    resp = client.post("/focus/complete", data={"minutes": "25"}, follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert resp.headers["location"] == "/today"

    db_session.refresh(day)
    assert day.status == "done"
    assert day.logged_minutes == 25.0


def test_focus_complete_minimal_true_marks_day_minimal(client, unique, db_session):
    _onboard_and_register(client, unique, "deep_focus", 60, length_days=60)
    season = db_session.exec(select(Season).order_by(Season.id.desc())).first()
    day = _force_today_as_train_day(db_session, season)

    client.post("/focus/complete", data={"minutes": "4", "minimal": "true"}, follow_redirects=False)
    db_session.refresh(day)
    assert day.status == "minimal"
    assert day.logged_minutes == 4.0


def test_sum_logged_minutes_since_last_measure(db_session, client, unique):
    _onboard_and_register(client, unique, "deep_focus", 60, length_days=60)
    season = db_session.exec(select(Season).order_by(Season.id.desc())).first()

    for day_number, minutes in ((2, 25.0), (3, 25.0), (4, None)):
        db_session.add(
            SeasonDay(
                season_id=season.id,
                day_number=day_number,
                calendar_date=season.start_date + timedelta(days=day_number - 1),
                kind="train",
                title="t",
                instructions="i",
                minimal_version="m",
                status="done" if minutes else "planned",
                logged_minutes=minutes,
            )
        )
    db_session.commit()

    total = sum_logged_minutes_since_last_measure(db_session, season, today_day_number=4)
    assert total == 50.0
