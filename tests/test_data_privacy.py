"""Экспорт и удаление данных, страница «Конфиденциальность» — PRD 1.0
«Безопасность и данные», доп. задача (см. docs/decisions/DECISIONS.md)."""

import json
from datetime import date

from sqlmodel import select

from app.models import Profile, Season, User

THIS_YEAR = date.today().year


def _register_payload(unique: str, **overrides):
    payload = {
        "name": "Данные Тест",
        "birth_year": THIS_YEAR - 25,
        "age_confirm": "1",
        "email": f"priv-{unique}@example.com",
        "login": f"priv-{unique}",
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


def test_privacy_page_renders_without_login(client):
    resp = client.get("/privacy")
    assert resp.status_code == 200
    assert "NewLife" in resp.text


def test_export_returns_json_with_own_data(client, unique, db_session):
    _register(client, unique)
    resp = client.get("/profile/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    data = json.loads(resp.text)
    assert data["user"]["login"] == f"priv-{unique}"
    assert "password_hash" not in data["user"]
    assert "profile" in data


def test_delete_account_requires_correct_password(client, unique, db_session):
    _register(client, unique)
    resp = client.post("/profile/delete-account", data={"password": "wrong-password", "confirm": "1"})
    assert resp.status_code == 200
    assert "Неверный пароль" in resp.text or "notoʻgʻri" in resp.text

    user = db_session.exec(select(User).where(User.login == f"priv-{unique}")).first()
    assert user is not None  # аккаунт не удалён


def test_delete_account_requires_confirmation_checkbox(client, unique, db_session):
    _register(client, unique)
    resp = client.post("/profile/delete-account", data={"password": "s3cret-pass", "confirm": ""})
    assert resp.status_code == 200

    user = db_session.exec(select(User).where(User.login == f"priv-{unique}")).first()
    assert user is not None


def test_delete_account_removes_user_and_related_data(client, unique, db_session):
    _register(client, unique)
    user = db_session.exec(select(User).where(User.login == f"priv-{unique}")).first()
    uid = user.id
    assert db_session.exec(select(Profile).where(Profile.uid == uid)).first() is not None

    resp = client.post(
        "/profile/delete-account", data={"password": "s3cret-pass", "confirm": "1"}, follow_redirects=False
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"

    db_session.expire_all()
    assert db_session.exec(select(User).where(User.id == uid)).first() is None
    assert db_session.exec(select(Profile).where(Profile.uid == uid)).first() is None
    assert db_session.exec(select(Season).where(Season.uid == uid)).first() is None

    # Сессия должна быть очищена — повторный заход на /profile редиректит на логин.
    whoami = client.get("/profile", follow_redirects=False)
    assert whoami.status_code in (302, 303)
