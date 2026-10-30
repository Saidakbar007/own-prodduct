"""Роуты Telegram (§12, Фаза 3): Mini App auth, привязка аккаунта, webhook."""

import hashlib
import hmac
import json
from datetime import date
from urllib.parse import urlencode

BOT_TOKEN = "123456:TEST-TOKEN-not-real"
THIS_YEAR = date.today().year


def _signed_init_data(tg_id: int, bot_token: str = BOT_TOKEN) -> str:
    fields = {"auth_date": "1700000000", "user": json.dumps({"id": tg_id, "first_name": "Т"})}
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


def test_telegram_auth_without_bot_token_configured_returns_503(client, monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    resp = client.post("/telegram/auth", data={"init_data": "whatever"})
    assert resp.status_code == 503


def test_telegram_auth_rejects_bad_signature(client, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", BOT_TOKEN)
    resp = client.post("/telegram/auth", data={"init_data": "auth_date=1&user=%7B%7D&hash=deadbeef"})
    assert resp.status_code == 401


def test_telegram_auth_unknown_user_redirects_to_link_page(client, monkeypatch, unique):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", BOT_TOKEN)
    init_data = _signed_init_data(tg_id=900001)
    resp = client.post("/telegram/auth", data={"init_data": init_data}, follow_redirects=True)
    assert resp.status_code == 200
    assert "Привет из Telegram" in resp.text


def test_link_existing_account_via_telegram(client, monkeypatch, unique):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", BOT_TOKEN)

    # Сначала обычная регистрация обычным путём.
    client.post(
        "/register",
        data={
            "name": "Телеграм Тестов",
            "birth_year": str(THIS_YEAR - 25),
            "age_confirm": "1",
            "email": f"tg-{unique}@example.com",
            "login": f"tg-{unique}",
            "password": "s3cret-pass",
            "password_confirm": "s3cret-pass",
            "timezone": "UTC",
        },
    )
    client.get("/logout")

    init_data = _signed_init_data(tg_id=900002)
    client.post("/telegram/auth", data={"init_data": init_data})

    link_resp = client.post(
        "/telegram/link/existing",
        data={"login": f"tg-{unique}", "password": "s3cret-pass"},
        follow_redirects=True,
    )
    assert link_resp.status_code == 200

    # Повторная авторизация через тот же Telegram id теперь сразу узнаёт пользователя
    client.get("/logout")
    second_auth = client.post("/telegram/auth", data={"init_data": init_data}, follow_redirects=True)
    assert second_auth.status_code == 200
    assert "Привет из Telegram" not in second_auth.text  # сразу прошли в приложение, не на экран привязки


def test_webhook_rejects_missing_secret(client, monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "real-secret")
    resp = client.post("/telegram/webhook", json={"message": {"text": "/start", "chat": {"id": 1}, "from": {"id": 1}}})
    assert resp.status_code == 401


def test_webhook_accepts_correct_secret(client, monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "real-secret")
    resp = client.post(
        "/telegram/webhook",
        json={"message": {"text": "/start", "chat": {"id": 1}, "from": {"id": 1}}},
        headers={"X-Telegram-Bot-Api-Secret-Token": "real-secret"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
