"""События метрик (§13, Фаза 4) — запись и то, что основные роуты их шлют."""

from datetime import date, datetime, timezone

from sqlmodel import select

from app.models import Event
from app.services.events import log_event, log_event_safe

THIS_YEAR = date.today().year


def test_log_event_stores_meta_as_json(db_session):
    event = log_event(db_session, "day_done", uid=1, season_id=2, meta={"foo": "bar"})
    assert event.id is not None
    assert event.meta_json == '{"foo": "bar"}'


def test_log_event_safe_never_raises(db_session, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("db is down")

    monkeypatch.setattr("app.services.events.log_event", boom)
    log_event_safe(db_session, "day_done")  # не должно бросить исключение


def test_onboarding_and_registration_emit_funnel_events(client, unique, db_session):
    marker = datetime.now(timezone.utc)
    client.get("/onboarding")
    client.post("/onboarding/goal", data={"template_id": "run_5k"})
    client.post("/onboarding/baseline", data={"value": "5"})
    client.post("/onboarding/schedule", data={"length_days": "60"})
    client.get("/onboarding/trailer")
    client.post(
        "/register",
        data={
            "name": "Событие Тестов",
            "birth_year": str(THIS_YEAR - 25),
            "age_confirm": "1",
            "email": f"ev-{unique}@example.com",
            "login": f"ev-{unique}",
            "password": "s3cret-pass",
            "password_confirm": "s3cret-pass",
            "timezone": "UTC",
        },
    )

    types = set(
        db_session.exec(select(Event.event_type).where(Event.created_at >= marker)).all()
    )
    for expected in ("onboarding_started", "trailer_shown", "signup"):
        assert expected in types
    # prologue_started либо season_started — в зависимости от дня недели теста
    assert "prologue_started" in types or "season_started" in types
