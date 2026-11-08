"""Лестница ступеней (confidence_through_action, public_speaking_confidence) —
доп. задача, см. app/newlife/goal_catalog.py::LadderSpec и
docs/decisions/DECISIONS.md → «Этап "Доделай" + guide + wger»."""

from datetime import date

from sqlmodel import select

from app.models import Season

THIS_YEAR = date.today().year


def _register_payload(unique: str, **overrides):
    payload = {
        "name": "Лестница Тест",
        "birth_year": THIS_YEAR - 25,
        "age_confirm": "1",
        "email": f"ladder-{unique}@example.com",
        "login": f"ladder-{unique}",
        "password": "s3cret-pass",
        "password_confirm": "s3cret-pass",
        "timezone": "UTC",
    }
    payload.update(overrides)
    return payload


def _start_ladder_season(client, unique):
    client.post("/onboarding/goal", data={"template_id": "confidence_through_action"})
    client.post("/onboarding/baseline", data={"value": "2"})
    client.post("/onboarding/schedule", data={"length_days": "60"})
    client.get("/onboarding/trailer")
    reg = client.post("/register", data=_register_payload(unique), follow_redirects=True)
    assert reg.status_code == 200
    return client.get("/season", follow_redirects=True)


def test_season_detail_shows_first_rung(client, unique):
    _start_ladder_season(client, unique)
    season_page = client.get("/season", follow_redirects=True)
    assert season_page.status_code == 200
    assert "незнакомого человека" in season_page.text


def test_ladder_advance_moves_to_next_rung_and_cannot_skip_ahead(client, unique, db_session):
    _start_ladder_season(client, unique)
    season = db_session.exec(select(Season).order_by(Season.id.desc())).first()
    assert season.ladder_rung == 1

    resp = client.post(f"/season/{season.id}/ladder/advance", follow_redirects=False)
    assert resp.status_code == 303
    db_session.refresh(season)
    assert season.ladder_rung == 2

    # Один вызов — продвижение ровно на одну ступень, не больше.
    resp2 = client.post(f"/season/{season.id}/ladder/advance", follow_redirects=False)
    assert resp2.status_code == 303
    db_session.refresh(season)
    assert season.ladder_rung == 3


def test_ladder_advance_stops_at_last_rung(client, unique, db_session):
    _start_ladder_season(client, unique)
    season = db_session.exec(select(Season).order_by(Season.id.desc())).first()
    total_rungs = 7  # confidence_through_action: 7 ступеней (расширено по NEWLIFE_KNOWLEDGE_BASE.md)

    for _ in range(total_rungs + 3):
        client.post(f"/season/{season.id}/ladder/advance", follow_redirects=False)
    db_session.refresh(season)
    assert season.ladder_rung == total_rungs


def test_ladder_skip_does_not_advance(client, unique, db_session):
    _start_ladder_season(client, unique)
    season = db_session.exec(select(Season).order_by(Season.id.desc())).first()

    resp = client.post(f"/season/{season.id}/ladder/skip", follow_redirects=False)
    assert resp.status_code == 303
    db_session.refresh(season)
    assert season.ladder_rung == 1
