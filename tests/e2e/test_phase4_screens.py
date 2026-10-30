"""E2E для экранов Фазы 4 (§13, §14): админка — 375px, обе темы."""

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.test_phase2_screens import VIEWPORT, _set_theme

THEMES = ["dark", "light"]
SCREENSHOT_DIR = Path(__file__).parent.parent.parent / "design_review" / "final"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def _shoot(page: Page, name: str, theme: str) -> None:
    page.screenshot(path=str(SCREENSHOT_DIR / f"{name}-{theme}.png"), full_page=True)


def _register_admin(page: Page, live_server_url: str, login: str) -> None:
    page.goto(f"{live_server_url}/register")
    page.fill("#name", "Админ Тестов")
    page.fill("#birth_year", "1996")
    page.fill("#email", f"{login}@example.com")
    page.fill("#login", login)
    page.fill("#password", "s3cret-pass")
    page.fill("#password_confirm", "s3cret-pass")
    page.check('input[name="age_confirm"]')
    page.click('button[type="submit"]')


@pytest.mark.parametrize("theme", THEMES)
def test_admin_dashboard_screen(page: Page, live_server_url, monkeypatch, theme):
    login = f"adm-dash-{theme}"
    monkeypatch.setenv("ADMIN_LOGINS", login)
    _register_admin(page, live_server_url, login)

    page.set_viewport_size(VIEWPORT)
    page.goto(f"{live_server_url}/admin")
    _set_theme(page, theme)
    expect(page.get_by_role("heading", name="Воронка и удержание")).to_be_visible()
    _shoot(page, "admin-dashboard", theme)


@pytest.mark.parametrize("theme", THEMES)
def test_admin_gallery_screen(page: Page, live_server_url, monkeypatch, theme):
    login = f"adm-gal-{theme}"
    monkeypatch.setenv("ADMIN_LOGINS", login)
    _register_admin(page, live_server_url, login)

    page.set_viewport_size(VIEWPORT)
    page.goto(f"{live_server_url}/admin/gallery")
    _set_theme(page, theme)
    expect(page.get_by_role("heading", name="Сезоны — галерея шаблонов")).to_be_visible()
    _shoot(page, "admin-gallery", theme)


@pytest.mark.parametrize("theme", THEMES)
def test_admin_sandbox_screen(page: Page, live_server_url, monkeypatch, theme):
    login = f"adm-sbx-{theme}"
    monkeypatch.setenv("ADMIN_LOGINS", login)
    _register_admin(page, live_server_url, login)

    page.set_viewport_size(VIEWPORT)
    page.goto(f"{live_server_url}/admin/sandbox")
    _set_theme(page, theme)
    expect(page.get_by_role("heading", name="Песочница")).to_be_visible()
    _shoot(page, "admin-sandbox", theme)
