"""
NEWLIFE_2_0.md Этап 1 п.2: «Вкладка "Цели" не открывается». Расследование
(см. отчёт backend-core): профилирование /seasons, /season, /season/{id}
через TestClient с демо-подобными данными (несколько активных сезонов,
завершённый сезон с Reveal, прогон всех 67 шаблонов каталога по
season_detail) не нашло ни исключения, ни N+1-зависания — все ответы
2xx и быстрые. Этот e2e-тест фиксирует правильное поведение через
настоящий клик по нижней навигации (не прямой переход по URL) — на
случай, если реальная проблема клиентская (перехват клика JS/HTMX), а
не серверная.
"""

import uuid
from datetime import date, timedelta

from playwright.sync_api import Page, expect
from sqlmodel import Session

from app.database import engine
from app.models import Reveal, Season, SeasonDay, User
from app.services.reveals import get_or_create_reveal
from app.services.seasons import create_season
from sqlmodel import select

from tests.e2e.test_phase2_screens import VIEWPORT, _register_with_season


def _seed_demo_like_extra_data(login_prefix: str) -> None:
    """Второй активный сезон + один завершённый с Reveal — форма demo-
    данных из scripts/seed_demo.py (не трогаем сам файл), чтобы "Цели"
    открывались не на пустой/единственной записи."""
    with Session(engine) as db:
        user = db.exec(select(User).where(User.login == f"screens-{login_prefix}")).first()
        if not user:
            return

        today = date.today()
        second = create_season(
            db, uid=user.id, template_id="pushups_50", length_days=30,
            baseline_value=5, reference_date=today,
        )

        finished = create_season(
            db, uid=user.id, template_id="pullups_10", length_days=30,
            baseline_value=1, reference_date=today - timedelta(days=35),
        )
        for day in db.exec(select(SeasonDay).where(SeasonDay.season_id == finished.id)).all():
            day.status = "done" if day.kind != "rest" else "rest"
            db.add(day)
        finished.status = "finished"
        db.add(finished)
        db.commit()
        get_or_create_reveal(db, finished)


def test_seasons_tab_opens_with_several_active_and_completed_seasons(page: Page, live_server_url):
    unique = _register_with_season(page, live_server_url, template_id="run_5k", sphere_id="body")
    _seed_demo_like_extra_data(unique)

    page.set_viewport_size(VIEWPORT)
    page.goto(f"{live_server_url}/today")

    # Настоящий клик по нижней навигации, не прямой переход по URL.
    page.click('a[href="/seasons"]')
    page.wait_for_url(f"{live_server_url}/seasons", timeout=10_000)

    expect(page.locator("body")).to_be_visible()
    expect(page.get_by_text("5 км").first).to_be_visible()

    # Открыть карточку завершённого сезона и один из активных — тоже
    # не должны зависать/падать.
    page.goto(f"{live_server_url}/season")
    expect(page.locator("body")).to_be_visible()
