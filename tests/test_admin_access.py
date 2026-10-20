"""
Тесты доступа к админке (v6d): только логины из ADMIN_LOGINS, остальным —
404 (не редирект/403), ссылка "Админка" видна только админам.
"""

from sqlmodel import select

from app.models import User
from app.services.admin import admin_logins, is_admin
from tests.conftest import register_user


def test_admin_logins_parses_comma_separated(monkeypatch):
    monkeypatch.setenv("ADMIN_LOGINS", "demo, admin2 ,boss")
    assert admin_logins() == {"demo", "admin2", "boss"}


def test_admin_logins_defaults_to_demo_in_local_dev_when_unset(monkeypatch):
    monkeypatch.delenv("ADMIN_LOGINS", raising=False)
    monkeypatch.delenv("RENDER", raising=False)
    assert admin_logins() == {"demo"}


def test_admin_logins_empty_on_render_when_unset(monkeypatch):
    """На проде (Render сам выставляет RENDER=true) дефолт на demo не срабатывает — нужен настоящий ADMIN_LOGINS."""
    monkeypatch.delenv("ADMIN_LOGINS", raising=False)
    monkeypatch.setenv("RENDER", "true")
    assert admin_logins() == set()


def test_is_admin_true_for_listed_login(client, session, monkeypatch):
    monkeypatch.setenv("ADMIN_LOGINS", "adminuser")
    register_user(client, login="adminuser", mail="adminuser@example.com")
    user = session.exec(select(User).where(User.login == "adminuser")).first()
    assert is_admin(user) is True


def test_is_admin_false_for_unlisted_login(client, session, monkeypatch):
    monkeypatch.setenv("ADMIN_LOGINS", "someoneelse")
    register_user(client, login="regular1", mail="regular1@example.com")
    user = session.exec(select(User).where(User.login == "regular1")).first()
    assert is_admin(user) is False


def test_is_admin_false_for_none_user(monkeypatch):
    monkeypatch.setenv("ADMIN_LOGINS", "someone")
    assert is_admin(None) is False


def test_non_admin_gets_404_on_admin_page(client, session, monkeypatch):
    monkeypatch.setenv("ADMIN_LOGINS", "onlythisone")
    register_user(client, login="regular2", mail="regular2@example.com")
    resp = client.get("/admin")
    assert resp.status_code == 404


def test_guest_gets_404_on_admin_page(client, monkeypatch):
    monkeypatch.setenv("ADMIN_LOGINS", "someone")
    resp = client.get("/admin")
    assert resp.status_code == 404


def test_admin_gets_200_on_admin_page(client, session, monkeypatch):
    monkeypatch.setenv("ADMIN_LOGINS", "superadmin")
    register_user(client, login="superadmin", mail="superadmin@example.com")
    resp = client.get("/admin")
    assert resp.status_code == 200


def test_admin_link_hidden_for_regular_user(client, session, monkeypatch):
    monkeypatch.setenv("ADMIN_LOGINS", "onlyadmin")
    register_user(client, login="regular3", mail="regular3@example.com")
    resp = client.get("/")
    assert resp.status_code == 200
    assert "/admin" not in resp.text


def test_admin_link_visible_for_admin_user(client, session, monkeypatch):
    monkeypatch.setenv("ADMIN_LOGINS", "visibleadmin")
    register_user(client, login="visibleadmin", mail="visibleadmin@example.com")
    resp = client.get("/")
    assert resp.status_code == 200
    assert 'href="/admin"' in resp.text
