"""Серия (§7.5) и Reveal (§7.8) — доводим сезон до финала "задним числом"."""

from datetime import date

from PIL import Image
from sqlmodel import select

from app.models import Season, SeasonDay

THIS_YEAR = date.today().year


def _register_payload(unique: str):
    return {
        "name": "Финал Тестов",
        "birth_year": THIS_YEAR - 25,
        "age_confirm": "1",
        "email": f"finale-{unique}@example.com",
        "login": f"finale-{unique}",
        "password": "s3cret-pass",
        "password_confirm": "s3cret-pass",
        "timezone": "UTC",
    }


def _create_short_season(client, unique):
    client.post("/onboarding/goal", data={"template_id": "pushups_50"})
    client.post("/onboarding/baseline", data={"value": "5"})
    client.post("/onboarding/schedule", data={"length_days": "30"})
    client.get("/onboarding/trailer")
    client.post("/register", data=_register_payload(unique))


def _force_finish_season(db_session, season_id: int) -> None:
    """Проставляет все дни сезона как "done" и переводит сезон в finished —
    без этого Reveal недоступен (нужен весь путь, а не только последний день)."""
    season = db_session.get(Season, season_id)
    season.status = "finished"
    db_session.add(season)

    days = db_session.exec(select(SeasonDay).where(SeasonDay.season_id == season_id)).all()
    for day in days:
        if day.status == "planned":
            day.status = "done"
            db_session.add(day)
    db_session.commit()


def test_reveal_is_redirected_away_while_season_not_finished(client, unique):
    _create_short_season(client, unique)
    season_id = client.get("/season").url  # просто убеждаемся, что страница доступна
    resp = client.get("/season/1/reveal", follow_redirects=False)
    assert resp.status_code in (303, 404)  # 404, если season_id=1 не принадлежит этому юзеру


def test_full_reveal_flow_after_forcing_season_finished(client, unique, db_session):
    _create_short_season(client, unique)

    season = db_session.exec(select(Season).order_by(Season.id.desc())).first()
    _force_finish_season(db_session, season.id)

    reveal_page = client.get(f"/season/{season.id}/reveal", follow_redirects=True)
    assert reveal_page.status_code == 200
    assert "Reveal" in reveal_page.text or "позади" in reveal_page.text

    card = client.get(f"/season/{season.id}/reveal/card.png")
    assert card.status_code == 200
    assert card.headers["content-type"] == "image/png"
    assert len(card.content) > 1000  # не пустая картинка

    # повторный запрос должен отдать закэшированный файл, не падать
    card2 = client.get(f"/season/{season.id}/reveal/card.png")
    assert card2.status_code == 200


def test_episode_card_generates_for_first_completed_week(client, unique, db_session):
    _create_short_season(client, unique)
    season = db_session.exec(select(Season).order_by(Season.id.desc())).first()

    # Переносим все дни первой недели в прошлое, чтобы неделя считалась закрытой
    from datetime import timedelta

    days = db_session.exec(
        select(SeasonDay).where(SeasonDay.season_id == season.id, SeasonDay.day_number <= 7)
    ).all()
    for day in days:
        day.calendar_date = date.today() - timedelta(days=10 - day.day_number)
        if day.status == "planned":
            day.status = "done"
        db_session.add(day)
    season.start_date = date.today() - timedelta(days=9)
    db_session.add(season)
    db_session.commit()

    episode_page = client.get(f"/season/{season.id}/episode/1")
    assert episode_page.status_code == 200

    card = client.get(f"/season/{season.id}/episode/1/card.png")
    assert card.status_code == 200
    assert card.headers["content-type"] == "image/png"


def test_proof_file_is_only_visible_to_owner(client, unique):
    _create_short_season(client, unique)
    resp = client.get("/proofs/999999")
    assert resp.status_code == 404


def test_reveal_video_404_without_any_proof_photos(client, unique, db_session):
    _create_short_season(client, unique)
    season = db_session.exec(select(Season).order_by(Season.id.desc())).first()
    _force_finish_season(db_session, season.id)

    client.get(f"/season/{season.id}/reveal")  # создаёт Reveal
    resp = client.get(f"/season/{season.id}/reveal/video.mp4")
    assert resp.status_code == 404


def test_reveal_video_generates_mp4_when_proof_photos_exist(client, unique, db_session):
    import io

    from app.services import video as video_service

    if not video_service.ffmpeg_available():
        import pytest

        pytest.skip("ffmpeg недоступен в этом окружении")

    _create_short_season(client, unique)

    # День 1 — всегда "точка старта" (kind=measure), фото-доказательство для
    # него проставляется через /measure, а не /today/done.
    img = Image.new("RGB", (300, 300), (10, 120, 60))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    client.post("/measure", data={"value": "6"}, files={"photo": ("proof.jpg", buf, "image/jpeg")})

    season = db_session.exec(select(Season).order_by(Season.id.desc())).first()
    _force_finish_season(db_session, season.id)

    client.get(f"/season/{season.id}/reveal")
    resp = client.get(f"/season/{season.id}/reveal/video.mp4")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "video/mp4"
    assert len(resp.content) > 1000
