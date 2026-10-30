"""Вызов «Спорим?» (§7 п.7, Фаза 3) — создание, принятие, спор/подтверждение."""

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import select

import app.main
from app.models import Challenge, Season, SeasonDay
from app.services.challenges import (
    confirm_dispute,
    counted_progress,
    create_challenge,
    determine_winner,
    dispute_day,
)
from app.services.seasons import create_season

THIS_YEAR = date.today().year


def _register_payload(login: str):
    return {
        "name": f"Дуэль {login}",
        "birth_year": THIS_YEAR - 25,
        "age_confirm": "1",
        "email": f"{login}@example.com",
        "login": login,
        "password": "s3cret-pass",
        "password_confirm": "s3cret-pass",
        "timezone": "UTC",
    }


def test_create_and_join_challenge_full_flow(unique):
    client_a = TestClient(app.main.app)
    client_b = TestClient(app.main.app)

    # Пользователь A: онбординг + сезон
    client_a.post("/onboarding/goal", data={"template_id": "run_5k"})
    client_a.post("/onboarding/baseline", data={"value": "5"})
    client_a.post("/onboarding/schedule", data={"length_days": "60"})
    client_a.get("/onboarding/trailer")
    client_a.post("/register", data=_register_payload(f"duel-a-{unique}"))

    create_resp = client_a.post("/challenge/create", follow_redirects=True)
    assert create_resp.status_code == 200
    assert "Ждём, когда соперник" in create_resp.text

    from app.database import engine
    from sqlmodel import Session

    with Session(engine) as db:
        challenge = db.exec(select(Challenge).order_by(Challenge.id.desc())).first()
        invite_code = challenge.invite_code
        challenge_id = challenge.id

    # Пользователь B: свой сезон того же шаблона, затем принимает вызов
    client_b.post("/onboarding/goal", data={"template_id": "run_5k"})
    client_b.post("/onboarding/baseline", data={"value": "3"})
    client_b.post("/onboarding/schedule", data={"length_days": "60"})
    client_b.get("/onboarding/trailer")
    client_b.post("/register", data=_register_payload(f"duel-b-{unique}"))

    join_page = client_b.get(f"/challenge/join/{invite_code}")
    assert join_page.status_code == 200
    assert "Принять вызов" in join_page.text

    accept_resp = client_b.post(f"/challenge/join/{invite_code}/accept", follow_redirects=True)
    assert accept_resp.status_code == 200
    assert "Дуэль" in accept_resp.text

    # Создатель вызова тоже видит активную дуэль
    duel_resp = client_a.get(f"/challenge/{challenge_id}")
    assert duel_resp.status_code == 200
    assert "Дуэль" in duel_resp.text


def test_dispute_excludes_day_from_tally_until_confirmed(db_session, unique):
    from datetime import date as date_cls

    today = date_cls(2026, 11, 2)  # понедельник
    from app.auth import hash_password
    from app.models import User

    def make_user(login):
        u = User(login=login, email=f"{login}@example.com", password_hash=hash_password("pw"), name=login, birth_year=1995)
        db_session.add(u)
        db_session.commit()
        db_session.refresh(u)
        return u

    u1 = make_user(f"disp-a-{unique}")
    u2 = make_user(f"disp-b-{unique}")
    s1 = create_season(db_session, u1.id, "run_5k", 60, 5, today)
    s2 = create_season(db_session, u2.id, "run_5k", 60, 5, today)

    # помечаем день 1 обоих как done
    for sid in (s1.id, s2.id):
        day = db_session.exec(select(SeasonDay).where(SeasonDay.season_id == sid, SeasonDay.day_number == 1)).first()
        day.status = "done"
        db_session.add(day)
    db_session.commit()

    challenge = create_challenge(db_session, u1.id, s1.id)
    challenge.to_uid = u2.id
    challenge.season_id_to = s2.id
    challenge.status = "active"
    db_session.add(challenge)
    db_session.commit()
    db_session.refresh(challenge)

    before = counted_progress(db_session, s1.id, challenge.id, u1.id)
    assert before >= 1

    dispute = dispute_day(db_session, challenge.id, day_number=1, uid=u1.id, disputed_by=u2.id)
    after = counted_progress(db_session, s1.id, challenge.id, u1.id)
    assert after == before - 1  # спорный день временно не засчитывается

    confirm_dispute(db_session, dispute)
    restored = counted_progress(db_session, s1.id, challenge.id, u1.id)
    assert restored == before  # после подтверждения — снова засчитывается


def test_determine_winner_picks_higher_count(db_session, unique):
    from datetime import date as date_cls

    today = date_cls(2026, 11, 2)
    from app.auth import hash_password
    from app.models import User

    def make_user(login):
        u = User(login=login, email=f"{login}@example.com", password_hash=hash_password("pw"), name=login, birth_year=1995)
        db_session.add(u)
        db_session.commit()
        db_session.refresh(u)
        return u

    u1 = make_user(f"win-a-{unique}")
    u2 = make_user(f"win-b-{unique}")
    s1 = create_season(db_session, u1.id, "pushups_50", 30, 5, today)
    s2 = create_season(db_session, u2.id, "pushups_50", 30, 5, today)

    for day_number in (1, 3):
        day = db_session.exec(select(SeasonDay).where(SeasonDay.season_id == s1.id, SeasonDay.day_number == day_number)).first()
        if day:
            day.status = "done"
            db_session.add(day)
    db_session.commit()

    challenge = create_challenge(db_session, u1.id, s1.id)
    challenge.to_uid = u2.id
    challenge.season_id_to = s2.id
    challenge.status = "active"
    db_session.add(challenge)
    db_session.commit()
    db_session.refresh(challenge)

    assert determine_winner(db_session, challenge) == u1.id


def test_determine_winner_none_without_opponent(db_session, unique):
    from app.auth import hash_password
    from app.models import User

    u1 = User(login=f"solo-{unique}", email=f"solo-{unique}@example.com", password_hash=hash_password("pw"), name="Solo", birth_year=1995)
    db_session.add(u1)
    db_session.commit()
    db_session.refresh(u1)
    s1 = create_season(db_session, u1.id, "run_5k", 60, 5, date.today())

    challenge = create_challenge(db_session, u1.id, s1.id)
    assert determine_winner(db_session, challenge) is None
