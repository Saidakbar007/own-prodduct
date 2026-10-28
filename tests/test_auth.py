"""Регистрация, вход, выход."""

from datetime import date

THIS_YEAR = date.today().year


def _register_payload(unique: str, **overrides):
    payload = {
        "name": "Тест Тестов",
        "birth_year": THIS_YEAR - 20,
        "age_confirm": "1",
        "email": f"user-{unique}@example.com",
        "login": f"user-{unique}",
        "password": "s3cret-pass",
        "password_confirm": "s3cret-pass",
        "timezone": "UTC",
    }
    payload.update(overrides)
    return payload


def test_register_success_logs_in_and_shows_greeting(client, unique):
    resp = client.post("/register", data=_register_payload(unique), follow_redirects=True)
    assert resp.status_code == 200
    assert "Тест Тестов" in resp.text


def test_register_without_age_confirm_is_rejected(client, unique):
    payload = _register_payload(unique)
    del payload["age_confirm"]
    resp = client.post("/register", data=payload)
    assert resp.status_code == 200
    assert "18" in resp.text


def test_register_under_18_is_rejected(client, unique):
    payload = _register_payload(unique, birth_year=THIS_YEAR - 10)
    resp = client.post("/register", data=payload)
    assert resp.status_code == 200
    assert "18" in resp.text
    # пользователь не должен был быть создан — логин свободен для следующей попытки
    login_resp = client.post(
        "/login", data={"login": payload["login"], "password": payload["password"]}
    )
    assert "Неверный логин" in login_resp.text


def test_register_password_mismatch_is_rejected(client, unique):
    resp = client.post("/register", data=_register_payload(unique, password_confirm="other"))
    assert "не совпадают" in resp.text


def test_register_duplicate_login_or_email_is_rejected(client, unique):
    payload = _register_payload(unique)
    first = client.post("/register", data=payload)
    assert first.status_code in (200, 303)

    other_client_payload = _register_payload(unique)  # тот же login/email, другой клиент
    import app.main  # noqa: F401
    from fastapi.testclient import TestClient

    second_client = TestClient(app.main.app)
    resp = second_client.post("/register", data=other_client_payload)
    assert "уже используются" in resp.text


def test_login_success_and_logout(client, unique):
    payload = _register_payload(unique)
    client.post("/register", data=payload)
    client.get("/logout")

    login_resp = client.post(
        "/login",
        data={"login": payload["login"], "password": payload["password"]},
        follow_redirects=True,
    )
    assert payload["name"] in login_resp.text

    client.get("/logout")
    home = client.get("/")
    assert payload["name"] not in home.text


def test_login_wrong_password_is_rejected(client, unique):
    payload = _register_payload(unique)
    client.post("/register", data=payload)
    client.get("/logout")

    resp = client.post("/login", data={"login": payload["login"], "password": "wrong"})
    assert "Неверный логин" in resp.text


def test_guest_home_shows_cta(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Сезоны" in resp.text


def test_unknown_page_returns_branded_404(client):
    resp = client.get("/this-page-does-not-exist")
    assert resp.status_code == 404
    assert "не найдена" in resp.text
