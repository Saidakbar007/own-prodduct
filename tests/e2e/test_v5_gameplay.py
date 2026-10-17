"""
E2e-тесты v5: автоопределение часового пояса при регистрации, выбор
привычки из каталога/своей, пятиугольная диаграмма героя на главной.
"""

import re


def test_register_autofills_browser_timezone(page, e2e_server):
    page.goto(f"{e2e_server}/register")
    page.wait_for_function("document.getElementById('timezone-input').value !== 'UTC'")
    value = page.input_value("#timezone-input")
    assert "/" in value  # похоже на IANA-зону вида Region/City, не просто "UTC"


def test_create_habit_from_catalog(demo_page, e2e_server):
    demo_page.goto(f"{e2e_server}/habits")
    demo_page.wait_for_load_state("networkidle")

    # по умолчанию открыта вкладка "Из каталога"
    demo_page.select_option("#catalog-select", "water")
    demo_page.click('button:has-text("Добавить привычку")')
    demo_page.wait_for_load_state("networkidle")

    assert "Пить воду" in demo_page.content()


def test_create_custom_habit_requires_sphere_selection(demo_page, e2e_server):
    demo_page.goto(f"{e2e_server}/habits")
    demo_page.click("#tab-custom")
    demo_page.fill('input[name="name"]', "Уникальная привычка E2E")
    demo_page.select_option("#custom-sphere", "charisma")
    demo_page.click('button:has-text("Добавить привычку")')
    demo_page.wait_for_load_state("networkidle")

    assert "Уникальная привычка E2E" in demo_page.content()


def test_homepage_shows_hero_pentagon_chart(demo_page, e2e_server):
    demo_page.goto(f"{e2e_server}/")
    demo_page.wait_for_load_state("networkidle")

    chart_text = demo_page.locator("text=Профиль героя")
    assert chart_text.count() > 0

    svg = demo_page.locator("svg[aria-label='Диаграмма сфер героя']").first
    assert svg.is_visible()
    # 5 сфер -> 5 подписей внутри диаграммы
    labels = svg.locator("text[data-sphere]")
    assert labels.count() == 5


def test_profile_shows_timezone_and_change_form(demo_page, e2e_server):
    demo_page.goto(f"{e2e_server}/profile")
    demo_page.wait_for_load_state("networkidle")

    assert "Часовой пояс" in demo_page.content()
    tz_input = demo_page.locator('input[name="timezone"]').last
    assert tz_input.input_value() != ""
