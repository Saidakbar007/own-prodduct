"""NEWLIFE_2_0.md §3.2 (Задача 3): роудмап-«тропа» на детальной странице
сезона — только для сфер Тело/Разум/Энергия. 375px, тёмная и светлая тема."""

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.test_phase2_screens import THEMES, VIEWPORT, _register_with_season, _set_theme

SCREENSHOT_DIR = Path(__file__).parent.parent.parent / "docs" / "design" / "design_review" / "final"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


@pytest.mark.parametrize("theme", THEMES)
def test_season_roadmap_visible_for_body_sphere(page: Page, live_server_url, theme):
    """run_5k (body, 5 фаз в YAML) — роудмап с маркером "Ты здесь"."""
    _register_with_season(page, live_server_url, template_id="run_5k", sphere_id="body")
    page.set_viewport_size(VIEWPORT)
    page.goto(f"{live_server_url}/season")
    _set_theme(page, theme)
    expect(page.locator(".roadmap")).to_be_visible()
    expect(page.get_by_text("Ты здесь")).to_be_visible()
    page.screenshot(path=str(SCREENSHOT_DIR / f"season-roadmap-body-{theme}.png"), full_page=True)


def test_season_roadmap_visible_for_mind_sphere(page: Page, live_server_url):
    """deep_focus (mind, 1 фаза в YAML) — тропа по неделям, тоже с "Ты здесь"."""
    _register_with_season(page, live_server_url, template_id="deep_focus", sphere_id="mind")
    page.set_viewport_size(VIEWPORT)
    page.goto(f"{live_server_url}/season")
    expect(page.locator(".roadmap")).to_be_visible()
    expect(page.get_by_text("Ты здесь")).to_be_visible()


def test_season_roadmap_absent_for_other_spheres(page: Page, live_server_url):
    """programming (career) — вне Задачи 3, роудмап не показывается (экран
    сезона остаётся как был)."""
    _register_with_season(page, live_server_url, template_id="programming", sphere_id="career")
    page.set_viewport_size(VIEWPORT)
    page.goto(f"{live_server_url}/season")
    expect(page.locator(".calendar-grid")).to_be_visible()
    expect(page.locator(".roadmap")).to_have_count(0)
