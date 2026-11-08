"""
NEWLIFE_2_0.md Этап 1 п.3: «Аккаунт не сохраняется» — после входа онбординг
не должен повторяться. Сессия должна жить достаточно долго (90 дней,
app/main.py — SessionMiddleware max_age) и переживать «новый контекст
браузера с теми же cookies» (новый TestClient = новый процесс/вкладка,
но тот же signed cookie).
"""

from datetime import date

from fastapi.testclient import TestClient

from app.main import app

THIS_YEAR = date.today().year


def _register_payload(unique: str, **overrides):
    payload = {
        "name": "Сессия Тест",
        "birth_year": THIS_YEAR - 25,
        "age_confirm": "1",
        "email": f"sess-{unique}@example.com",
        "login": f"sess-{unique}",
        "password": "s3cret-pass",
        "password_confirm": "s3cret-pass",
        "timezone": "UTC",
    }
    payload.update(overrides)
    return payload


def test_login_persists_across_new_client_with_same_cookies(client, unique):
    """Войти -> новый TestClient с теми же cookies (эмуляция «закрыл и открыл
    заново») -> /today сразу открывается, без редиректа на /onboarding."""
    client.post("/onboarding/goal", data={"template_id": "run_5k"})
    client.post("/onboarding/baseline", data={"value": "5"})
    client.post("/onboarding/schedule", data={"length_days": "60"})
    client.get("/onboarding/trailer")

    register_resp = client.post("/register", data=_register_payload(unique), follow_redirects=True)
    assert register_resp.status_code == 200

    # Новый "браузер" (новый TestClient = новый процесс), но те же signed
    # cookies — ровно то, что происходит при повторном открытии сайта/
    # Telegram Mini App, если сессия сохраняется правильно.
    fresh_client = TestClient(app, cookies=dict(client.cookies))

    today_resp = fresh_client.get("/today", follow_redirects=False)
    assert today_resp.status_code == 200
    assert "onboarding" not in (today_resp.headers.get("location") or "")

    # Содержимое — экран "Сегодня", не анкета/философия онбординга.
    assert "Начни с себя" not in today_resp.text


def test_login_submit_reuses_existing_session_without_onboarding(client, unique):
    """/login (не только /register) не должен ронять уже заполненный
    профиль обратно в онбординг при повторном входе."""
    client.post("/onboarding/goal", data={"template_id": "pushups_50"})
    client.post("/onboarding/baseline", data={"value": "5"})
    client.post("/onboarding/schedule", data={"length_days": "30"})
    client.get("/onboarding/trailer")
    payload = _register_payload(unique, login=f"login2-{unique}", email=f"login2-{unique}@example.com")
    client.post("/register", data=payload, follow_redirects=True)
    client.get("/logout")

    login_client = TestClient(app, cookies=dict(client.cookies))
    login_resp = login_client.post(
        "/login", data={"login": payload["login"], "password": payload["password"]}, follow_redirects=True
    )
    assert login_resp.status_code == 200
    assert "День 1" in login_resp.text or "Сегодня" in login_resp.text


def test_session_cookie_max_age_is_ninety_days(client):
    """NEWLIFE_2_0.md Этап 1 п.3: cookie сессии должна жить 90 дней, не
    дефолтные 14 у Starlette."""
    resp = client.get("/onboarding")
    set_cookie = resp.headers.get("set-cookie", "")
    assert "Max-Age=7776000" in set_cookie  # 90 * 24 * 60 * 60
