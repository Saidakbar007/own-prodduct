"""
UX-прогон (ветка `ux`): один сценарий нового пользователя (регистрация →
первый сезон → первое действие дня → все вкладки) плюс демо-аккаунт,
375 px, светлая и тёмная тема. Скриншоты — в design_review/ux/<UX_SHOTS>/
(переменная окружения UX_SHOTS=before|after, по умолчанию "after").

Селекторы держим на id полей форм и ролях — они переживают переписывание
копирайта экранов между "до" и "после".
"""

import os
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from playwright.sync_api import Page
from sqlmodel import Session, select

from app.auth import hash_password
from app.database import engine
from app.models import Measurement, SeasonDay, User
from app.services.reveals import get_or_create_reveal
from app.services.seasons import build_all_days, create_season

THEMES = ["dark", "light"]
VIEWPORT = {"width": 375, "height": 812}
SHOT_SUBDIR = os.environ.get("UX_SHOTS", "after")
DEMO_LOGIN = "ux-demo"
DEMO_PASSWORD = "UxDemo2026!"


def _shots_dir():
    from pathlib import Path

    d = Path(__file__).parent.parent.parent / "design_review" / "ux" / SHOT_SUBDIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def _set_theme(page: Page, theme: str) -> None:
    page.evaluate("t => document.documentElement.setAttribute('data-theme', t)", theme)


def _shoot(page: Page, name: str, theme: str) -> None:
    page.screenshot(path=str(_shots_dir() / f"{name}-{theme}.png"), full_page=True)


def _goto_first_ok(page: Page, base_url: str, paths: tuple[str, ...]) -> None:
    """Пробует пути по очереди (новый → старый роут), берёт первый не-404."""
    last = paths[-1]
    for path in paths:
        resp = page.goto(f"{base_url}{path}")
        last = path
        if resp is not None and resp.status != 404:
            return
    page.goto(f"{base_url}{last}")


def _register_new_user(page: Page, live_server_url: str, template_id: str = "pushups_50") -> str:
    """Онбординг с нуля → регистрация. pushups_50 — без доп. health-шага."""
    unique = uuid.uuid4().hex[:8]
    page.goto(f"{live_server_url}/onboarding")
    page.locator(f'input[name="template_id"][value="{template_id}"]').locator("..").locator(
        'button[type="submit"]'
    ).click()
    page.fill("#value", "5")
    page.click('button[type="submit"]')
    page.click('input[type="radio"] >> nth=0')
    page.click('button[type="submit"]')

    page.goto(f"{live_server_url}/register")
    page.fill("#name", f"UX Тест {unique}")
    page.fill("#birth_year", "1996")
    page.fill("#email", f"ux-{unique}@example.com")
    page.fill("#login", f"ux-{unique}")
    page.fill("#password", "s3cret-pass")
    page.fill("#password_confirm", "s3cret-pass")
    page.check('input[name="age_confirm"]')
    page.click('button[type="submit"]')
    return unique


@pytest.mark.parametrize("theme", THEMES)
def test_ux_new_user_journey(page: Page, live_server_url, theme):
    _register_new_user(page, live_server_url)
    page.set_viewport_size(VIEWPORT)
    _set_theme(page, theme)

    # 1. "Сегодня" сразу после регистрации — главный экран первого дня.
    page.goto(f"{live_server_url}/today")
    _set_theme(page, theme)
    _shoot(page, "01-today", theme)

    # 2. Первое действие дня (если есть форма "Сделал" — отмечаем).
    done_form = page.locator('form[action="/today/done"]')
    if done_form.count():
        done_form.locator('button[type="submit"]').click()
        _set_theme(page, theme)
        _shoot(page, "02-today-done", theme)
    else:
        _shoot(page, "02-today-done", theme)

    # 3. Вкладка "Сезон(ы)".
    _goto_first_ok(page, live_server_url, ("/seasons", "/season"))
    _set_theme(page, theme)
    _shoot(page, "03-season", theme)

    # 4. Вкладка "Команда"/"Состав".
    _goto_first_ok(page, live_server_url, ("/team", "/squad"))
    _set_theme(page, theme)
    _shoot(page, "04-team", theme)

    # 5. Профиль.
    page.goto(f"{live_server_url}/profile")
    _set_theme(page, theme)
    _shoot(page, "05-profile", theme)


def _ensure_demo_account() -> None:
    """Повторяет scripts/seed_demo.py прямо на тестовой БД (без повторного запуска
    миграций — они уже применены фикстурой `_migrated_app`)."""
    with Session(engine) as db:
        if db.exec(select(User).where(User.login == DEMO_LOGIN)).first():
            return
        demo = User(
            login=DEMO_LOGIN,
            email="ux-demo@example.com",
            password_hash=hash_password(DEMO_PASSWORD),
            name="Демо Демченко",
            birth_year=1995,
            timezone="Asia/Tashkent",
        )
        db.add(demo)
        db.commit()
        db.refresh(demo)

        today = date.today()
        season = create_season(
            db, uid=demo.id, template_id="run_5k", length_days=60,
            baseline_value=5, reference_date=today - timedelta(days=11),
        )
        build_all_days(db, season)
        days = db.exec(
            select(SeasonDay).where(SeasonDay.season_id == season.id).order_by(SeasonDay.day_number)
        ).all()
        for day in days:
            if day.calendar_date >= today or day.kind == "rest":
                continue
            day.status = "done"
            day.done_at = datetime.now(timezone.utc)
            db.add(day)
        db.add(Measurement(season_id=season.id, day_number=7, value=8.0))
        db.commit()

        season2 = create_season(
            db, uid=demo.id, template_id="pushups_50", length_days=30,
            baseline_value=5, reference_date=today - timedelta(days=35),
        )
        build_all_days(db, season2)
        days2 = db.exec(
            select(SeasonDay).where(SeasonDay.season_id == season2.id).order_by(SeasonDay.day_number)
        ).all()
        for day in days2:
            if day.status == "rest":
                continue
            day.status = "done"
            day.done_at = datetime.now(timezone.utc)
            db.add(day)
        season2.status = "finished"
        db.add(season2)
        db.add(Measurement(season_id=season2.id, day_number=30, value=38.0))
        db.commit()
        db.refresh(season2)
        get_or_create_reveal(db, season2)


@pytest.mark.parametrize("theme", THEMES)
def test_ux_demo_account(page: Page, live_server_url, theme):
    _ensure_demo_account()
    page.set_viewport_size(VIEWPORT)
    page.goto(f"{live_server_url}/login")
    page.fill("#login", DEMO_LOGIN)
    page.fill("#password", DEMO_PASSWORD)
    page.click('button[type="submit"]')
    _set_theme(page, theme)

    page.goto(f"{live_server_url}/today")
    _set_theme(page, theme)
    _shoot(page, "06-demo-today", theme)

    _goto_first_ok(page, live_server_url, ("/seasons", "/season"))
    _set_theme(page, theme)
    _shoot(page, "07-demo-season", theme)

    _goto_first_ok(page, live_server_url, ("/team", "/squad"))
    _set_theme(page, theme)
    _shoot(page, "08-demo-team", theme)

    page.goto(f"{live_server_url}/profile")
    _set_theme(page, theme)
    _shoot(page, "09-demo-profile", theme)
