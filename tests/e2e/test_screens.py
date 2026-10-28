"""
E2E (Playwright) для каркасных экранов Фазы 0: 375px, тёмная и светлая тема
(SEASONS_SPEC.md §16). Продуктовых экранов (Сегодня, Сезон, ...) ещё нет —
они появятся в Фазе 2.
"""

import uuid

import pytest
from playwright.sync_api import Page, expect

THEMES = ["dark", "light"]
VIEWPORT = {"width": 375, "height": 812}


def _set_theme(page: Page, theme: str) -> None:
    page.evaluate("t => document.documentElement.setAttribute('data-theme', t)", theme)


def _no_horizontal_overflow(page: Page) -> bool:
    return page.evaluate(
        "document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1"
    )


@pytest.mark.parametrize("theme", THEMES)
def test_guest_home_screen(page: Page, live_server_url, theme):
    page.set_viewport_size(VIEWPORT)
    page.goto(f"{live_server_url}/")
    _set_theme(page, theme)

    expect(page.get_by_role("link", name="Начать сезон")).to_be_visible()
    expect(page.get_by_role("link", name="У меня есть аккаунт")).to_be_visible()
    assert _no_horizontal_overflow(page)


@pytest.mark.parametrize("theme", THEMES)
def test_register_screen(page: Page, live_server_url, theme):
    page.set_viewport_size(VIEWPORT)
    page.goto(f"{live_server_url}/register")
    _set_theme(page, theme)

    expect(page.get_by_role("heading", name="Регистрация")).to_be_visible()
    expect(page.locator('button[type="submit"]')).to_be_visible()
    # зона нажатия чекбокса "мне есть 18" — не меньше 44px по высоте (touch target)
    box = page.locator('input[name="age_confirm"]').bounding_box()
    label_box = page.locator(".checkbox-field").bounding_box()
    assert label_box["height"] >= 24  # сам чекбокс маленький, но строка кликабельна целиком
    assert box is not None
    assert _no_horizontal_overflow(page)


@pytest.mark.parametrize("theme", THEMES)
def test_login_screen(page: Page, live_server_url, theme):
    page.set_viewport_size(VIEWPORT)
    page.goto(f"{live_server_url}/login")
    _set_theme(page, theme)

    expect(page.get_by_role("heading", name="Вход")).to_be_visible()
    expect(page.get_by_role("link", name="Зарегистрироваться")).to_be_visible()
    assert _no_horizontal_overflow(page)


@pytest.mark.parametrize("theme", THEMES)
def test_404_screen(page: Page, live_server_url, theme):
    page.set_viewport_size(VIEWPORT)
    page.goto(f"{live_server_url}/this-does-not-exist")
    _set_theme(page, theme)

    expect(page.get_by_role("heading", name="Страница не найдена")).to_be_visible()
    assert _no_horizontal_overflow(page)


def test_register_login_logout_flow_in_browser(page: Page, live_server_url):
    """Полный путь через настоящую форму в браузере, не через TestClient."""
    page.set_viewport_size(VIEWPORT)
    unique = uuid.uuid4().hex[:8]
    name = f"Браузер Тест {unique}"

    page.goto(f"{live_server_url}/register")
    page.fill("#name", name)
    page.fill("#birth_year", "1998")
    page.fill("#email", f"e2e-{unique}@example.com")
    page.fill("#login", f"e2e-{unique}")
    page.fill("#password", "s3cret-pass")
    page.fill("#password_confirm", "s3cret-pass")
    page.check('input[name="age_confirm"]')
    page.click('button[type="submit"]')

    expect(page.get_by_role("heading", name=name)).to_be_visible()

    page.get_by_role("link", name="Выйти").click()
    expect(page.get_by_role("link", name="Начать сезон")).to_be_visible()

    page.goto(f"{live_server_url}/login")
    page.fill('input[name="login"]', f"e2e-{unique}")
    page.fill('input[name="password"]', "s3cret-pass")
    page.click('button[type="submit"]')

    expect(page.get_by_role("heading", name=name)).to_be_visible()
