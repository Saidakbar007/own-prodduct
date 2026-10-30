"""E2E для новых экранов Фазы 3 (§7 п.7, §12): 375px, обе темы, скриншоты в design_review/final/."""

import hashlib
import hmac
import json
import uuid
from pathlib import Path
from urllib.parse import urlencode

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.test_phase2_screens import VIEWPORT, _register_with_season, _set_theme

THEMES = ["dark", "light"]
SCREENSHOT_DIR = Path(__file__).parent.parent.parent / "design_review" / "final"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

BOT_TOKEN = "123456:TEST-TOKEN-not-real"


def _shoot(page: Page, name: str, theme: str) -> None:
    page.screenshot(path=str(SCREENSHOT_DIR / f"{name}-{theme}.png"), full_page=True)


def _signed_init_data(tg_id: int) -> str:
    fields = {"auth_date": "1700000000", "user": json.dumps({"id": tg_id, "first_name": "Т"})}
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


@pytest.mark.parametrize("theme", THEMES)
def test_telegram_link_screen(page: Page, live_server_url, monkeypatch, theme):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", BOT_TOKEN)
    init_data = _signed_init_data(tg_id=uuid.uuid4().int % 1_000_000_000)

    page.request.post(f"{live_server_url}/telegram/auth", form={"init_data": init_data})
    page.set_viewport_size(VIEWPORT)
    page.goto(f"{live_server_url}/telegram/link")
    _set_theme(page, theme)
    expect(page.get_by_role("heading", name="Привет из Telegram")).to_be_visible()
    _shoot(page, "telegram-link", theme)


@pytest.mark.parametrize("theme", THEMES)
def test_challenge_waiting_screen(page: Page, live_server_url, theme):
    _register_with_season(page, live_server_url)
    page.set_viewport_size(VIEWPORT)
    page.goto(f"{live_server_url}/season")
    page.click('button:has-text("Вызвать друга")')
    _set_theme(page, theme)
    expect(page.get_by_role("heading", name="Дуэль")).to_be_visible()
    _shoot(page, "challenge-waiting", theme)


@pytest.mark.parametrize("theme", THEMES)
def test_challenge_active_duel_screen(page: Page, live_server_url, theme):
    _register_with_season(page, live_server_url, template_id="pullups_10")
    page.goto(f"{live_server_url}/season")
    page.click('button:has-text("Вызвать друга")')
    invite_link = page.locator("p").last.inner_text()

    second_page = page.context.new_page()
    _register_with_season(second_page, live_server_url, template_id="pullups_10")
    second_page.goto(f"{live_server_url}{invite_link}")
    second_page.click('button:has-text("Принять вызов")')

    page.set_viewport_size(VIEWPORT)
    page.goto(page.url)
    _set_theme(page, theme)
    expect(page.locator(".grid-2")).to_be_visible()
    _shoot(page, "challenge-duel", theme)
