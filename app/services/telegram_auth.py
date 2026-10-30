"""
Проверка подписи Telegram Mini App initData (§12 ТЗ) — HMAC-SHA256 по
алгоритму из документации Telegram. Без этого Mini App мог бы подделать
"я такой-то пользователь" произвольным запросом.
"""

import hashlib
import hmac
import json
from typing import Optional
from urllib.parse import parse_qsl


def verify_init_data(init_data: str, bot_token: str) -> Optional[dict]:
    """Возвращает распарсенные поля initData, если подпись верна, иначе None."""
    if not init_data or not bot_token:
        return None
    try:
        pairs = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        return None

    received_hash = pairs.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        return None
    return pairs


def telegram_user_from_init_data(verified: dict) -> Optional[dict]:
    """Поле "user" в initData — JSON-строка с id/first_name и т.д."""
    raw = verified.get("user")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None
