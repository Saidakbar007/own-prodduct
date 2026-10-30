"""Telegram (§12, Фаза 3) — проверка initData, бот: тихие часы, кнопки."""

import hashlib
import hmac
import json
from datetime import time
from urllib.parse import urlencode

import pytest

from app.services.telegram_auth import telegram_user_from_init_data, verify_init_data
from app.services.telegram_bot import (
    action_keyboard,
    is_quiet_hours,
)

BOT_TOKEN = "123456:TEST-TOKEN-not-real"


def _make_init_data(fields: dict, bot_token: str = BOT_TOKEN) -> str:
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    full = dict(fields)
    full["hash"] = computed_hash
    return urlencode(full)


def test_verify_init_data_accepts_correctly_signed_payload():
    fields = {"auth_date": "1700000000", "user": json.dumps({"id": 42, "first_name": "Диёр"})}
    init_data = _make_init_data(fields)
    result = verify_init_data(init_data, BOT_TOKEN)
    assert result is not None
    assert result["auth_date"] == "1700000000"


def test_verify_init_data_rejects_tampered_payload():
    fields = {"auth_date": "1700000000", "user": json.dumps({"id": 42})}
    init_data = _make_init_data(fields)
    tampered = init_data.replace("1700000000", "1700000001")
    assert verify_init_data(tampered, BOT_TOKEN) is None


def test_verify_init_data_rejects_wrong_bot_token():
    fields = {"auth_date": "1700000000", "user": json.dumps({"id": 42})}
    init_data = _make_init_data(fields, bot_token=BOT_TOKEN)
    assert verify_init_data(init_data, "different-token") is None


def test_verify_init_data_rejects_missing_hash():
    assert verify_init_data("auth_date=123&user=%7B%7D", BOT_TOKEN) is None


def test_verify_init_data_handles_empty_input():
    assert verify_init_data("", BOT_TOKEN) is None
    assert verify_init_data("something", "") is None


def test_telegram_user_from_init_data_parses_json():
    verified = {"user": json.dumps({"id": 7, "first_name": "А"})}
    parsed = telegram_user_from_init_data(verified)
    assert parsed == {"id": 7, "first_name": "А"}


def test_telegram_user_from_init_data_missing_field():
    assert telegram_user_from_init_data({}) is None


@pytest.mark.parametrize(
    "hour,minute,expected",
    [
        (23, 0, True),
        (23, 30, True),
        (2, 0, True),
        (7, 59, True),
        (8, 0, False),
        (8, 1, False),
        (22, 59, False),
        (12, 0, False),
    ],
)
def test_is_quiet_hours(hour, minute, expected):
    assert is_quiet_hours(time(hour, minute)) is expected


def test_action_keyboard_has_three_buttons_with_season_id():
    kb = action_keyboard(season_id=42)
    buttons = kb["inline_keyboard"][0]
    assert len(buttons) == 3
    assert all(b["callback_data"].endswith(":42") for b in buttons)
