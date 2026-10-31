"""
E2E для экранов Фазы 2 (§7, §16): 375px, тёмная и светлая тема.
Скриншоты сохраняются в design_review/final/ для визуальной проверки.
"""

import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect
from sqlmodel import select

from app.database import engine
from app.models import Season, SeasonDay
from sqlmodel import Session

THEMES = ["dark", "light"]
VIEWPORT = {"width": 375, "height": 812}
SCREENSHOT_DIR = Path(__file__).parent.parent.parent / "design_review" / "final"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def _set_theme(page: Page, theme: str) -> None:
    page.evaluate("t => document.documentElement.setAttribute('data-theme', t)", theme)


def _shoot(page: Page, name: str, theme: str) -> None:
    page.screenshot(path=str(SCREENSHOT_DIR / f"{name}-{theme}.png"), full_page=True)


def _register_with_season(page: Page, live_server_url: str, template_id: str = "run_5k") -> str:
    unique = uuid.uuid4().hex[:8]
    page.goto(f"{live_server_url}/onboarding")
    page.locator(f'input[name="template_id"][value="{template_id}"]').locator("..").locator(
        'button[type="submit"]'
    ).click()

    if template_id in ("fat_loss_safe", "muscle_gain"):
        page.fill("#height_cm", "178")
        page.fill("#weight_kg", "78")
        page.fill("#birth_year", "1996")
        page.click('button[type="submit"]')
        if template_id == "muscle_gain":
            page.fill("#value", "40")
            page.click('button[type="submit"]')
    else:
        page.fill("#value", "5")
        page.click('button[type="submit"]')

    page.click('input[type="radio"] >> nth=0')
    page.click('button[type="submit"]')

    page.goto(f"{live_server_url}/register")
    page.fill("#name", f"Экран Тест {unique}")
    page.fill("#birth_year", "1996")
    page.fill("#email", f"screens-{unique}@example.com")
    page.fill("#login", f"screens-{unique}")
    page.fill("#password", "s3cret-pass")
    page.fill("#password_confirm", "s3cret-pass")
    page.check('input[name="age_confirm"]')
    page.click('button[type="submit"]')
    return unique


@pytest.mark.parametrize("theme", THEMES)
def test_today_screen(page: Page, live_server_url, theme):
    _register_with_season(page, live_server_url)
    page.set_viewport_size(VIEWPORT)
    page.goto(f"{live_server_url}/today")
    _set_theme(page, theme)
    expect(page.locator("body")).to_be_visible()
    _shoot(page, "today", theme)


@pytest.mark.parametrize("theme", THEMES)
def test_season_screen(page: Page, live_server_url, theme):
    _register_with_season(page, live_server_url)
    page.set_viewport_size(VIEWPORT)
    page.goto(f"{live_server_url}/season")
    _set_theme(page, theme)
    expect(page.locator(".calendar-grid")).to_be_visible()
    _shoot(page, "season", theme)


@pytest.mark.parametrize("theme", THEMES)
def test_measure_screen(page: Page, live_server_url, theme):
    _register_with_season(page, live_server_url)
    page.set_viewport_size(VIEWPORT)
    page.goto(f"{live_server_url}/measure")
    _set_theme(page, theme)
    expect(page.locator('input[name="value"]')).to_be_visible()
    _shoot(page, "measure", theme)


@pytest.mark.parametrize("theme", THEMES)
def test_team_screen(page: Page, live_server_url, theme):
    _register_with_season(page, live_server_url)
    page.set_viewport_size(VIEWPORT)
    page.goto(f"{live_server_url}/team")
    _set_theme(page, theme)
    expect(page.get_by_role("heading", name="Команда", exact=True)).to_be_visible()
    _shoot(page, "squad", theme)


@pytest.mark.parametrize("theme", THEMES)
def test_profile_screen(page: Page, live_server_url, theme):
    _register_with_season(page, live_server_url)
    page.set_viewport_size(VIEWPORT)
    page.goto(f"{live_server_url}/profile")
    _set_theme(page, theme)
    expect(page.locator(".hero-slot")).to_be_visible()
    _shoot(page, "profile", theme)


@pytest.mark.parametrize("theme", THEMES)
def test_onboarding_goal_screen(page: Page, live_server_url, theme):
    page.set_viewport_size(VIEWPORT)
    page.goto(f"{live_server_url}/onboarding")
    _set_theme(page, theme)
    expect(page.get_by_role("heading", name="Какой у тебя будет сезон?")).to_be_visible()
    _shoot(page, "onboarding-goal", theme)


@pytest.mark.parametrize("theme", THEMES)
def test_onboarding_trailer_screen(page: Page, live_server_url, theme):
    page.goto(f"{live_server_url}/onboarding")
    page.locator('input[name="template_id"][value="run_5k"]').locator("..").locator(
        'button[type="submit"]'
    ).click()
    page.fill("#value", "5")
    page.click('button[type="submit"]')
    page.click('input[type="radio"] >> nth=0')
    page.click('button[type="submit"]')

    page.set_viewport_size(VIEWPORT)
    _set_theme(page, theme)
    expect(page.get_by_role("link", name="Зарегистрироваться и начать")).to_be_visible()
    _shoot(page, "onboarding-trailer", theme)


@pytest.mark.parametrize("theme", THEMES)
def test_reveal_screen(page: Page, live_server_url, theme):
    _register_with_season(page, live_server_url, template_id="pushups_50")

    with Session(engine) as db:
        season = db.exec(select(Season).order_by(Season.id.desc())).first()
        season.status = "finished"
        db.add(season)
        days = db.exec(select(SeasonDay).where(SeasonDay.season_id == season.id)).all()
        for d in days:
            if d.status == "planned":
                d.status = "done"
                db.add(d)
        db.commit()
        season_id = season.id

    page.set_viewport_size(VIEWPORT)
    page.goto(f"{live_server_url}/season/{season_id}/reveal")
    _set_theme(page, theme)
    expect(page.locator(".reveal-screen")).to_be_visible()
    _shoot(page, "reveal", theme)


@pytest.mark.parametrize("theme", THEMES)
def test_episode_screen(page: Page, live_server_url, theme):
    _register_with_season(page, live_server_url, template_id="pullups_10")

    with Session(engine) as db:
        season = db.exec(select(Season).order_by(Season.id.desc())).first()
        days = db.exec(
            select(SeasonDay).where(SeasonDay.season_id == season.id, SeasonDay.day_number <= 7)
        ).all()
        for d in days:
            d.calendar_date = date.today() - timedelta(days=10 - d.day_number)
            if d.status == "planned":
                d.status = "done"
            db.add(d)
        season.start_date = date.today() - timedelta(days=9)
        db.add(season)
        db.commit()
        season_id = season.id

    page.set_viewport_size(VIEWPORT)
    page.goto(f"{live_server_url}/season/{season_id}/episode/1")
    _set_theme(page, theme)
    expect(page.locator("img")).to_be_visible()
    _shoot(page, "episode", theme)


@pytest.mark.parametrize("theme", THEMES)
def test_fat_loss_health_screen(page: Page, live_server_url, theme):
    page.goto(f"{live_server_url}/onboarding")
    page.locator('input[name="template_id"][value="fat_loss_safe"]').locator("..").locator(
        'button[type="submit"]'
    ).click()
    page.set_viewport_size(VIEWPORT)
    _set_theme(page, theme)
    expect(page.locator('input[name="height_cm"]')).to_be_visible()
    _shoot(page, "onboarding-health", theme)
