"""Тесты регистрации, входа, выхода и защиты страниц."""

from tests.conftest import register_user


def test_register_creates_user_and_logs_in(client):
    resp = register_user(client, login="alice", mail="alice@example.com")
    assert resp.status_code == 303
    assert resp.headers["location"] == "/onboarding"  # сразу залогинен, но сначала короткий онбординг

    home = client.get("/")
    assert home.status_code == 200
    assert "alice" in home.text


def test_register_duplicate_login_fails(client):
    register_user(client, login="bob", mail="bob1@example.com")
    client.get("/logout")
    resp = register_user(client, login="bob", mail="bob2@example.com")
    assert resp.status_code == 200  # форма повторно показана с ошибкой
    assert "уже используются" in resp.text


def test_login_logout(client):
    register_user(client, login="carol", mail="carol@example.com", password="mypassword")
    client.get("/logout")

    bad = client.post("/login", data={"login": "carol", "password": "wrong"})
    assert "Неверный логин" in bad.text

    good = client.post(
        "/login", data={"login": "carol", "password": "mypassword"}, follow_redirects=False
    )
    assert good.status_code == 303

    home = client.get("/")
    assert "carol" in home.text

    client.get("/logout")
    home_after_logout = client.get("/")
    assert "carol" not in home_after_logout.text


def test_protected_page_redirects_when_not_logged_in(client):
    resp = client.get("/profile", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


def test_protected_page_accessible_when_logged_in(client):
    register_user(client, login="dave", mail="dave@example.com")
    resp = client.get("/profile")
    assert resp.status_code == 200
