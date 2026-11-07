"""/workout — программа тренировки (ACSM фулбади) для дней тренировки
muscle_gain/fat_loss_safe, см. app/newlife/workout_programs.py и
docs/decisions/DECISIONS.md → «Этап "Доделай" + guide + wger»."""

from datetime import date

from sqlmodel import select

from app.models import Season, SeasonDay

THIS_YEAR = date.today().year


def _force_today_as_train_day(db_session, season) -> SeasonDay:
    """День 1 создаётся kind="measure" (точка старта, UX-правка) — форсируем
    его в "train" на месте, как в tests/test_metric_input.py."""
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


def _register_payload(unique: str, **overrides):
    payload = {
        "name": "Воркаут Тестов",
        "birth_year": THIS_YEAR - 25,
        "age_confirm": "1",
        "email": f"wo-{unique}@example.com",
        "login": f"wo-{unique}",
        "password": "s3cret-pass",
        "password_confirm": "s3cret-pass",
        "timezone": "UTC",
    }
    payload.update(overrides)
    return payload


def _start_muscle_gain_season(client, unique):
    client.post("/onboarding/goal", data={"template_id": "muscle_gain"})
    client.post(
        "/onboarding/health",
        data={"height_cm": "180", "weight_kg": "75", "birth_year": str(THIS_YEAR - 25)},
    )
    client.post("/onboarding/baseline", data={"value": "40"})
    client.post("/onboarding/schedule", data={"length_days": "90"})
    client.get("/onboarding/trailer")
    reg = client.post("/register", data=_register_payload(unique), follow_redirects=True)
    assert reg.status_code == 200


def test_workout_page_redirects_without_active_season(client):
    resp = client.get("/workout", follow_redirects=False)
    assert resp.status_code in (303, 307)


def test_workout_page_lists_program_exercises_on_a_training_day(client, unique, db_session):
    _start_muscle_gain_season(client, unique)
    season = db_session.exec(select(Season).order_by(Season.id.desc())).first()
    _force_today_as_train_day(db_session, season)

    resp = client.get("/workout")
    assert resp.status_code == 200
    assert "Фулбади" in resp.text


def test_logging_a_set_persists_weight_and_reps(client, unique, db_session):
    _start_muscle_gain_season(client, unique)
    season = db_session.exec(select(Season).order_by(Season.id.desc())).first()
    _force_today_as_train_day(db_session, season)

    post_resp = client.post(
        "/workout/log", data={"exercise_id": "squat", "weight_kg": "40", "reps": "10"}, follow_redirects=False
    )
    assert post_resp.status_code == 303

    page = client.get("/workout")
    assert page.status_code == 200
    assert "40" in page.text
