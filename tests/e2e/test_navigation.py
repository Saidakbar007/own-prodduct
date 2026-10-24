"""
E2E-тесты навигации: реальные клики в реальном браузере (Playwright).
Запускаются против настоящего uvicorn-сервера (см. conftest.py).
"""

import re


def test_demo_login_lands_on_dashboard(demo_page, e2e_server):
    demo_page.wait_for_selector("text=demo", timeout=5000)
    assert "demo" in demo_page.content()


def test_desktop_nav_links_navigate(demo_page, e2e_server):
    demo_page.set_viewport_size({"width": 1280, "height": 900})
    demo_page.goto(e2e_server)

    demo_page.click('a[href="/habits"]')
    demo_page.wait_for_url(re.compile(r".*/habits"))

    demo_page.click('a[href="/goals"]')
    demo_page.wait_for_url(re.compile(r".*/goals"))

    demo_page.click('a[href="/friends"]')
    demo_page.wait_for_url(re.compile(r".*/friends"))


def test_sidebar_link_navigates_on_desktop(demo_page, e2e_server):
    """На md+ ширине вторичные разделы — прямые ссылки в сайдбаре, без меню "Ещё"."""
    demo_page.set_viewport_size({"width": 1280, "height": 900})
    demo_page.goto(e2e_server)

    sidebar = demo_page.locator("aside").first
    sidebar.locator('a[href="/stats"]').first.click()
    demo_page.wait_for_url(re.compile(r".*/stats"))


def test_more_menu_closes_on_outside_click(demo_page, e2e_server):
    demo_page.set_viewport_size({"width": 1280, "height": 900})
    demo_page.goto(e2e_server)

    demo_page.locator("[data-more-toggle]").first.click()
    demo_page.locator(".more-menu.open").first.wait_for(state="visible", timeout=3000)

    demo_page.mouse.click(10, 10)
    demo_page.wait_for_selector(".more-menu.open", state="hidden", timeout=3000)


def test_more_menu_closes_on_escape(demo_page, e2e_server):
    demo_page.set_viewport_size({"width": 1280, "height": 900})
    demo_page.goto(e2e_server)

    demo_page.locator("[data-more-toggle]").first.click()
    demo_page.locator(".more-menu.open").first.wait_for(state="visible", timeout=3000)

    demo_page.keyboard.press("Escape")
    demo_page.wait_for_selector(".more-menu.open", state="hidden", timeout=3000)


def test_theme_toggle_switches_dark_class(demo_page, e2e_server):
    demo_page.set_viewport_size({"width": 1280, "height": 900})
    demo_page.goto(e2e_server)

    demo_page.locator("[data-more-toggle]").first.click()
    demo_page.locator('[data-theme-option="dark"]').first.click()

    demo_page.wait_for_function("document.documentElement.classList.contains('dark')", timeout=3000)
    # выбор темы закрывает меню — проверяем это тут же
    demo_page.wait_for_selector(".more-menu.open", state="hidden", timeout=3000)

    demo_page.locator("[data-more-toggle]").first.click()
    demo_page.locator('[data-theme-option="light"]').first.click()
    demo_page.wait_for_function("!document.documentElement.classList.contains('dark')", timeout=3000)


def test_bottom_nav_visible_and_clickable_at_375(demo_page, e2e_server):
    demo_page.set_viewport_size({"width": 375, "height": 700})
    demo_page.goto(e2e_server)

    bottom_nav = demo_page.locator("nav.fixed.bottom-0")
    bottom_nav.wait_for(state="visible", timeout=3000)

    habits_link = bottom_nav.locator('a[href="/habits"]').first
    habits_link.click()
    demo_page.wait_for_url(re.compile(r".*/habits"))


def test_bottom_nav_more_opens_sheet_at_375(demo_page, e2e_server):
    demo_page.set_viewport_size({"width": 375, "height": 700})
    demo_page.goto(e2e_server)

    bottom_nav = demo_page.locator("nav.fixed.bottom-0")
    bottom_nav.locator("[data-more-toggle]").first.click()

    # На странице два .more-menu (десктоп-дропдаун + мобильный лист) —
    # на 375px виден только один, берём именно видимый
    sheet = demo_page.locator(".more-menu.open:visible").first
    sheet.wait_for(state="visible", timeout=3000)

    profile_link = sheet.locator('a[href="/profile"]').first
    profile_link.click()
    demo_page.wait_for_url(re.compile(r".*/profile"))


def test_sidebar_clickable_while_flash_toast_visible(demo_page, e2e_server):
    """
    Баг (до перехода на сайдбар): тост (+X очков) и меню "Ещё" оба были в
    правом верхнем углу — тост мог перекрыть и заблокировать клики по меню.
    Теперь на md+ ширине проверяем, что тост не блокирует прямые ссылки
    сайдбара (он слева, а не в верхнем углу).
    """
    demo_page.set_viewport_size({"width": 1280, "height": 900})
    demo_page.goto(f"{e2e_server}/habits")

    demo_page.click('#tab-custom')
    demo_page.fill('input[name="name"]', "Toast overlap habit")
    demo_page.click('button:has-text("Добавить привычку")')
    demo_page.wait_for_load_state("networkidle")

    demo_page.click('a:has-text("Toast overlap habit")')
    demo_page.wait_for_load_state("networkidle")
    demo_page.click('button[name="kind"][value="done"]')
    demo_page.wait_for_load_state("networkidle")

    toast = demo_page.locator("#toasts")
    assert toast.is_visible()

    sidebar = demo_page.locator("aside").first
    sidebar.locator('a[href="/stats"]').first.click(timeout=3000)
    demo_page.wait_for_url(re.compile(r".*/stats"))


def test_check_habit_from_detail_page(demo_page, e2e_server):
    demo_page.set_viewport_size({"width": 1280, "height": 900})
    demo_page.goto(f"{e2e_server}/habits")

    first_habit_link = demo_page.locator('a[href^="/habits/"]').first
    first_habit_link.click()
    demo_page.wait_for_load_state("networkidle")

    # Если сегодня ещё не отмечено — жмём "Выполнено полностью"/"Не сорвался"
    done_button = demo_page.locator('button[name="kind"][value="done"]').first
    if done_button.count() > 0:
        done_button.click()
        demo_page.wait_for_load_state("networkidle")

    assert "Сегодня уже отмечено" in demo_page.content() or "Отметить" in demo_page.content()
