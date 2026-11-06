"""
NewLife v8 — прогон (ветка `v8`, docs/specs/NEWLIFE_V8_SPEC.md §16): полный сценарий
нового пользователя через все 12 экранов онбординга (точка А → цель →
режим дня → обязательные дела → ... → WOOP → раскрытие → регистрация) и
demo-аккаунт с заполненными данными по всем модулям v8. Скриншоты — 375px,
светлая и тёмная тема, в design_review/v8/.
"""

import json
import os
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from playwright.sync_api import Page
from sqlmodel import Session, select

from app.auth import hash_password
from app.database import engine
from app.models import BadHabit, Commitment, Habit, Measurement, Profile, SeasonDay, SphereState, User
from app.services.checkin_service import log_checkin
from app.services.habits import log_bad_habit_slip, log_habit
from app.services.seasons import build_all_days, create_season

THEMES = ["dark", "light"]
VIEWPORT = {"width": 375, "height": 812}
DEMO_LOGIN = "v8-demo"
DEMO_PASSWORD = "V8Demo2026!"


def _shots_dir():
    from pathlib import Path

    d = Path(__file__).parent.parent.parent / "design_review" / "v8"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _set_theme(page: Page, theme: str) -> None:
    page.evaluate("t => document.documentElement.setAttribute('data-theme', t)", theme)


def _shoot(page: Page, name: str, theme: str) -> None:
    page.screenshot(path=str(_shots_dir() / f"{name}-{theme}.png"), full_page=True)


def _complete_onboarding_wizard(page: Page, base_url: str, template_id: str = "pushups_50") -> str:
    """Экраны 1-12 (§5) полностью, с нуля, до появления "раскрытия"."""
    page.goto(f"{base_url}/onboarding")  # экран 1: философия
    page.click('a[href="/onboarding/spheres"]')

    page.check('input[name="sphere_ids"][value="body"]')  # экран 2: сферы
    page.locator('form[action="/onboarding/spheres"]').first.locator('button[type="submit"]').click()

    page.locator(f'form[action="/onboarding/sphere-level"] button[type="submit"] >> nth=0').click()  # экран 3

    page.locator(f'form[action="/onboarding/goal"] input[value="{template_id}"]').locator("..").locator(
        'button[type="submit"]'
    ).click()  # экран 4: цель

    page.fill("#value", "5")  # экран: базовый замер
    page.click('button[type="submit"]')

    page.click('button[type="submit"]')  # экран: длина сезона (по умолчанию)

    page.click('form[action="/onboarding/mode"] button[type="submit"]')  # экран 6: режим дня

    page.locator('form[action="/onboarding/commitments"] input[name="action"][value="next"]').locator(
        ".."
    ).locator('button[type="submit"]').click()  # экран 7: обязательные дела — пропуск

    page.click('form[action="/onboarding/daily-minutes"] button[type="submit"]')  # экран 8
    page.click('form[action="/onboarding/chronotype"] button[type="submit"]')  # экран 9
    page.click('form[action="/onboarding/constraints"] button[type="submit"]')  # экран 10

    page.locator('form[action="/onboarding/woop/obstacle"] button[type="submit"] >> nth=0').click()  # экран 11
    page.click('form[action="/onboarding/woop"] button[type="submit"]')

    # экран 12: раскрытие — переход к регистрации (анонимный человек)
    page.click('a[href="/register"]')

    unique = uuid.uuid4().hex[:8]
    page.fill("#name", f"V8 Тест {unique}")
    page.fill("#birth_year", "1996")
    page.fill("#email", f"v8-{unique}@example.com")
    page.fill("#login", f"v8-{unique}")
    page.fill("#password", "s3cret-pass")
    page.fill("#password_confirm", "s3cret-pass")
    page.check('input[name="age_confirm"]')
    page.click('button[type="submit"]')
    return unique


@pytest.mark.parametrize("theme", THEMES)
def test_v8_new_user_onboarding_and_tabs(page: Page, live_server_url, theme):
    _complete_onboarding_wizard(page, live_server_url)
    page.set_viewport_size(VIEWPORT)
    _set_theme(page, theme)

    page.goto(f"{live_server_url}/today")
    _set_theme(page, theme)
    _shoot(page, "01-today", theme)

    page.goto(f"{live_server_url}/week")
    _set_theme(page, theme)
    _shoot(page, "02-week", theme)

    page.goto(f"{live_server_url}/seasons")
    _set_theme(page, theme)
    _shoot(page, "03-seasons", theme)

    page.goto(f"{live_server_url}/habits")
    _set_theme(page, theme)
    _shoot(page, "04-habits", theme)

    page.goto(f"{live_server_url}/profile")
    _set_theme(page, theme)
    _shoot(page, "05-profile", theme)

    page.goto(f"{live_server_url}/profile/wheel")
    _set_theme(page, theme)
    _shoot(page, "06-wheel", theme)


def _ensure_v8_demo_account() -> None:
    with Session(engine) as db:
        if db.exec(select(User).where(User.login == DEMO_LOGIN)).first():
            return
        demo = User(
            login=DEMO_LOGIN,
            email="v8-demo@example.com",
            password_hash=hash_password(DEMO_PASSWORD),
            name="NewLife Демо",
            birth_year=1994,
            timezone="Asia/Tashkent",
        )
        db.add(demo)
        db.commit()
        db.refresh(demo)

        profile = Profile(
            uid=demo.id, height_cm=178, weight_kg=68.0, wake_time="07:00", sleep_time="23:00",
            chronotype="morning", daily_minutes=30, constraints_json=json.dumps(["has_pullup_bar"]),
            main_obstacle="tired", onboarding_done_at=datetime.now(timezone.utc),
        )
        db.add(profile)
        for sphere_id in (
            "body", "mind", "character", "social", "career", "finance",
            "relationships", "knowledge", "values", "lifestyle", "energy",
        ):
            db.add(SphereState(
                uid=demo.id, sphere_id=sphere_id,
                level=6 if sphere_id == "body" else 4,
                priority=1 if sphere_id == "body" else 2,
                active=sphere_id == "body",
            ))
        db.commit()

        today = date.today()
        season = create_season(
            db, uid=demo.id, template_id="muscle_gain", length_days=90,
            baseline_value=68.0, secondary_baseline_value=60.0,
            reference_date=today - timedelta(days=16), sphere_id="body",
        )
        build_all_days(db, season)
        days = db.exec(
            select(SeasonDay).where(SeasonDay.season_id == season.id).order_by(SeasonDay.day_number)
        ).all()
        current_day_number = next(
            (d.day_number for d in days if d.calendar_date >= today), days[-1].day_number
        )
        for day in days:
            if day.day_number >= current_day_number or day.kind == "rest":
                continue
            day.status = "done"
            day.done_at = datetime.now(timezone.utc)
            db.add(day)
        db.add(Measurement(season_id=season.id, day_number=1, value=68.0))
        db.commit()

        db.add_all([
            Commitment(
                uid=demo.id, title="Учёба", category="study", weekdays_json=json.dumps([1, 2, 3, 4, 5]),
                start_time="09:00", end_time="13:00",
            ),
            Commitment(
                uid=demo.id, title="Работа", category="work", weekdays_json=json.dumps([1, 2, 3, 4, 5]),
                start_time="14:00", end_time="18:00",
            ),
        ])
        db.commit()

        habits = [
            Habit(
                uid=demo.id, catalog_id="water_morning", title="Стакан воды с утра",
                spheres_json=json.dumps(["body", "energy"]), days_json=json.dumps([1, 2, 3, 4, 5, 6, 7]),
                time_pref="morning", duration_min=2, minimal_version="Сделать хотя бы глоток",
            ),
            Habit(
                uid=demo.id, catalog_id="stretch_morning", title="Утренняя растяжка",
                spheres_json=json.dumps(["body"]), days_json=json.dumps([1, 2, 3, 4, 5, 6, 7]),
                time_pref="morning", duration_min=10, minimal_version="2 минуты растяжки",
            ),
            Habit(
                uid=demo.id, catalog_id="walk_daily", title="Дневная прогулка",
                spheres_json=json.dumps(["body", "energy"]), days_json=json.dumps([1, 2, 3, 4, 5, 6, 7]),
                time_pref="day", duration_min=20, minimal_version="5 минут на свежем воздухе",
            ),
        ]
        db.add_all(habits)
        db.commit()
        for h in habits:
            db.refresh(h)
        for offset in range(7, 0, -1):
            for h in habits:
                status = "missed" if offset == 4 else "done"
                log_habit(
                    db, habit_id=h.id, on_date=today - timedelta(days=offset),
                    status=status, now=datetime.now(timezone.utc),
                )

        bad_habit = BadHabit(
            uid=demo.id, catalog_id="social_media_scroll", title="Бесцельный скролл соцсетей",
            triggers_json=json.dumps(["boredom", "stress", "automatic", "procrastination"]),
            replacement_id="read_book", baseline_per_day=90.0, target_per_day=30.0, unit="minutes",
        )
        db.add(bad_habit)
        db.commit()
        db.refresh(bad_habit)
        for offset, minutes in zip(range(7, 0, -1), [85, 75, 70, 60, 55, 45, 40]):
            log = log_bad_habit_slip(
                db, bad_habit_id=bad_habit.id, on_date=today - timedelta(days=offset),
                trigger_id="boredom", now=datetime.now(timezone.utc),
            )
            log.value = float(minutes)
            db.add(log)
        db.commit()

        log_checkin(db, uid=demo.id, on_date=today - timedelta(days=1), energy=3, stress=3, mood=3)
        log_checkin(db, uid=demo.id, on_date=today, energy=4, stress=2, mood=4)


@pytest.mark.parametrize("theme", THEMES)
def test_v8_demo_account_tabs(page: Page, live_server_url, theme):
    _ensure_v8_demo_account()
    page.set_viewport_size(VIEWPORT)
    page.goto(f"{live_server_url}/login")
    page.fill("#login", DEMO_LOGIN)
    page.fill("#password", DEMO_PASSWORD)
    page.click('button[type="submit"]')
    _set_theme(page, theme)

    page.goto(f"{live_server_url}/today")
    _set_theme(page, theme)
    _shoot(page, "07-demo-today", theme)

    page.goto(f"{live_server_url}/week")
    _set_theme(page, theme)
    _shoot(page, "08-demo-week", theme)

    page.goto(f"{live_server_url}/seasons")
    _set_theme(page, theme)
    _shoot(page, "09-demo-seasons", theme)

    page.goto(f"{live_server_url}/habits")
    _set_theme(page, theme)
    _shoot(page, "10-demo-habits", theme)

    page.goto(f"{live_server_url}/profile")
    _set_theme(page, theme)
    _shoot(page, "11-demo-profile", theme)

    page.goto(f"{live_server_url}/profile/wheel")
    _set_theme(page, theme)
    _shoot(page, "12-demo-wheel", theme)
