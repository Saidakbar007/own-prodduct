"""
Тонкий клиент Telegram Bot API — без сторонней библиотеки, через httpx
(уже есть в зависимостях). Нужен TELEGRAM_BOT_TOKEN в окружении.
"""

import os
from typing import Optional

import httpx

API_BASE = "https://api.telegram.org/bot{token}/{method}"


def is_configured() -> bool:
    return bool(os.getenv("TELEGRAM_BOT_TOKEN"))


def _token() -> str:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN не задан")
    return token


def call(method: str, **params) -> dict:
    url = API_BASE.format(token=_token(), method=method)
    resp = httpx.post(url, json=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def send_message(chat_id: int, text: str, reply_markup: Optional[dict] = None) -> dict:
    params = {"chat_id": chat_id, "text": text}
    if reply_markup:
        params["reply_markup"] = reply_markup
    return call("sendMessage", **params)


def answer_callback_query(callback_query_id: str, text: str = "") -> dict:
    return call("answerCallbackQuery", callback_query_id=callback_query_id, text=text)


def set_webhook(url: str, secret_token: str) -> dict:
    return call("setWebhook", url=url, secret_token=secret_token, allowed_updates=["message", "callback_query"])


def set_my_commands(commands: list[dict]) -> dict:
    return call("setMyCommands", commands=commands)


def set_chat_menu_button(web_app_url: str, text: str = "Открыть Сезоны") -> dict:
    return call(
        "setChatMenuButton",
        menu_button={"type": "web_app", "text": text, "web_app": {"url": web_app_url}},
    )
