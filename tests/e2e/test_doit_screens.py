"""
E2E для новых/изменённых экранов этапа «Доделай + guide + wger» (см.
docs/decisions/DECISIONS.md): 375px, тёмная и светлая тема, ru.

Экраны: /workout, /flashcards (хаб + сессия), /expenses, /help,
/season/{id} (guide/лестница/банк вопросов/ресурсы), /focus (дыхание),
/today (кнопка "Открыть тренировку"; карточки "Недельная рефлексия" там
больше нет — NEWLIFE_2_0.md Этап 1 п.5, единственный опрос на "Сегодня" —
"вопрос дня").

Скриншоты — docs/design/design_review/1.0/doit/ (новая подпапка по
аналогии с final/, v8/, ux/).
"""

import uuid
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect
from sqlmodel import Session, select

from app.database import engine
from app.models import Season, SeasonDay, User
from tests.e2e.test_phase2_screens import VIEWPORT, _register_with_season, _set_theme

THEMES = ["dark", "light"]
SCREENSHOT_DIR = Path(__file__).parent.parent.parent / "docs" / "design" / "design_review" / "1.0" / "doit"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def _shoot(page: Page, name: str, theme: str) -> None:
    page.screenshot(path=str(SCREENSHOT_DIR / f"{name}-{theme}.png"), full_page=True)


def _register_minimal(page: Page, live_server_url: str) -> str:
    """Регистрация в обход мастера онбординга (PRD §register_submit
    допускает это явно) — для экранов, которым не нужна активная цель."""
    unique = uuid.uuid4().hex[:8]
    page.goto(f"{live_server_url}/register")
    page.fill("#name", f"Доделай Тест {unique}")
    page.fill("#birth_year", "1998")
    page.fill("#email", f"doit-{unique}@example.com")
    page.fill("#login", f"doit-{unique}")
    page.fill("#password", "s3cret-pass")
    page.fill("#password_confirm", "s3cret-pass")
    page.check('input[name="age_confirm"]')
    page.click('button[type="submit"]')
    return unique


def _force_day1_train(login: str, template_id: str) -> None:
    """День 1 создаётся kind="measure" (точка старта) — форсируем "train",
    как в tests/test_workout.py::_force_today_as_train_day."""
    with Session(engine) as db:
        user = db.exec(select(User).where(User.login == login)).first()
        season = db.exec(
            select(Season).where(Season.uid == user.id, Season.template_id == template_id)
        ).first()
        day = db.exec(
            select(SeasonDay).where(SeasonDay.season_id == season.id, SeasonDay.day_number == 1)
        ).first()
        day.kind = "train"
        day.status = "planned"
        db.add(day)
        db.commit()


# ---------------------------------------------------------------------------
# 1. /workout — программа тренировки + кнопка "Открыть тренировку" на /today
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("theme", THEMES)
def test_today_shows_open_workout_cta(page: Page, live_server_url, theme):
    """NEWLIFE_2_0.md Этап 1 п.5: «Недельная рефлексия» убрана с «Сегодня»
    (был второй опрос на экране, остался только «вопрос дня») — здесь
    проверяем, что CTA тренировки всё ещё на месте и карточки рефлексии
    точно нет."""
    unique = _register_with_season(page, live_server_url, template_id="muscle_gain", sphere_id="body")
    _force_day1_train(f"screens-{unique}", "muscle_gain")

    page.set_viewport_size(VIEWPORT)
    page.goto(f"{live_server_url}/today")
    _set_theme(page, theme)

    expect(page.get_by_role("link", name="Открыть тренировку")).to_be_visible()
    expect(page.get_by_text("Недельная рефлексия")).to_have_count(0)
    _shoot(page, "today-workout-reflection", theme)


@pytest.mark.parametrize("theme", THEMES)
def test_workout_page_shows_program_and_logs_a_set(page: Page, live_server_url, theme):
    unique = _register_with_season(page, live_server_url, template_id="muscle_gain", sphere_id="body")
    _force_day1_train(f"screens-{unique}", "muscle_gain")

    page.set_viewport_size(VIEWPORT)
    page.goto(f"{live_server_url}/workout")
    _set_theme(page, theme)

    expect(page.get_by_role("button", name="Зал")).to_be_visible()
    _shoot(page, "workout", theme)

    # переключатель зал/дом
    page.get_by_role("button", name="Дом").click()
    expect(page.get_by_role("button", name="Дом")).to_be_visible()

    # happy path: записать подход (вес + повторы) по первому упражнению
    first_form = page.locator('form[action="/workout/log"]').first
    first_form.locator('input[name="weight_kg"]').fill("20")
    first_form.locator('input[name="reps"]').fill("12")
    first_form.get_by_role("button", name="Записать").click()

    expect(page.locator('form[action="/workout/log"] input[name="weight_kg"]').first).to_have_value("20.0")


# ---------------------------------------------------------------------------
# 2. /flashcards — хаб и сессия повторения
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("theme", THEMES)
def test_flashcards_hub_screen(page: Page, live_server_url, theme):
    _register_minimal(page, live_server_url)
    page.set_viewport_size(VIEWPORT)
    page.goto(f"{live_server_url}/flashcards")
    _set_theme(page, theme)
    expect(page.get_by_role("heading", name="Карточки")).to_be_visible()
    expect(page.get_by_role("link").first).to_be_visible()
    _shoot(page, "flashcards-hub", theme)


@pytest.mark.parametrize("theme", THEMES)
def test_flashcards_session_pass_one_card(page: Page, live_server_url, theme):
    _register_minimal(page, live_server_url)
    page.set_viewport_size(VIEWPORT)
    page.goto(f"{live_server_url}/flashcards/english_b1")
    _set_theme(page, theme)

    expect(page.locator(".card").first).to_be_visible()
    _shoot(page, "flashcards-session-front", theme)

    page.get_by_role("button", name="Показать ответ").click()
    expect(page.get_by_role("button", name="Вспомнил(а)", exact=True)).to_be_visible()
    _shoot(page, "flashcards-session-revealed", theme)

    page.get_by_role("button", name="Вспомнил(а)", exact=True).click()
    # после отметки — снова сессия (следующая карточка либо "набор пройден")
    expect(page.locator("body")).to_be_visible()


# ---------------------------------------------------------------------------
# 3. /expenses — категории кнопками, степпер суммы, итог месяца
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("theme", THEMES)
def test_expenses_screen_log_and_see_total(page: Page, live_server_url, theme):
    _register_minimal(page, live_server_url)
    page.set_viewport_size(VIEWPORT)
    page.goto(f"{live_server_url}/expenses")
    _set_theme(page, theme)

    expect(page.locator("#expense-category-group")).to_be_visible()
    _shoot(page, "expenses", theme)

    page.locator('input[name="category"][value="transport"]').locator("..").click()
    amount_input = page.locator("#expense-amount")
    amount_input.fill("25000")
    page.get_by_role("button", name="Записать трату").click()

    expect(page.get_by_text("25000").first).to_be_visible()


# ---------------------------------------------------------------------------
# 4. /help — экран помощи (103/112)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("theme", THEMES)
def test_help_screen(page: Page, live_server_url, theme):
    _register_minimal(page, live_server_url)
    page.set_viewport_size(VIEWPORT)
    page.goto(f"{live_server_url}/help")
    _set_theme(page, theme)

    expect(page.locator('a[href="tel:103"]')).to_be_visible()
    expect(page.locator('a[href="tel:112"]')).to_be_visible()
    _shoot(page, "help", theme)


# ---------------------------------------------------------------------------
# 5. /season/{id} — guide, лестница вызовов, банк вопросов, ресурсы
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("theme", THEMES)
def test_season_detail_ladder_and_guide_visible_for_confidence_goal(page: Page, live_server_url, theme):
    unique = _register_with_season(
        page, live_server_url, template_id="confidence_through_action", sphere_id="character"
    )
    with Session(engine) as db:
        user = db.exec(select(User).where(User.login == f"screens-{unique}")).first()
        season = db.exec(select(Season).where(Season.uid == user.id)).first()
        season_id = season.id

    page.set_viewport_size(VIEWPORT)
    page.goto(f"{live_server_url}/season/{season_id}")
    _set_theme(page, theme)

    expect(page.get_by_text("Лестница вызовов")).to_be_visible()
    expect(page.get_by_text("Как это делать")).to_be_visible()
    # у этой цели нет банка вопросов и ресурсов
    expect(page.get_by_text("Банк вопросов для начала разговора")).not_to_be_visible()
    expect(page.get_by_text("Проверенные бесплатные ресурсы")).not_to_be_visible()
    _shoot(page, "season-detail-ladder", theme)


def test_season_detail_sections_are_goal_specific(page: Page, live_server_url):
    """Лестница/банк вопросов/ресурсы — только у своих целей (условная
    видимость, PRD «один движок — много контента»); у посторонней цели
    (run_5k) ни одной из трёх секций быть не должно."""
    _register_with_season(page, live_server_url, template_id="run_5k", sphere_id="body")
    page.set_viewport_size(VIEWPORT)
    page.goto(f"{live_server_url}/season")

    expect(page.get_by_text("Как это делать")).to_be_visible()
    expect(page.get_by_text("Лестница вызовов")).not_to_be_visible()
    expect(page.get_by_text("Банк вопросов для начала разговора")).not_to_be_visible()
    expect(page.get_by_text("Проверенные бесплатные ресурсы")).not_to_be_visible()


def test_season_detail_conversation_bank_visible_only_for_start_conversations(page: Page, live_server_url):
    _register_with_season(page, live_server_url, template_id="start_conversations", sphere_id="social")
    page.set_viewport_size(VIEWPORT)
    page.goto(f"{live_server_url}/season")

    expect(page.get_by_text("Банк вопросов для начала разговора")).to_be_visible()
    expect(page.get_by_text("Лестница вызовов")).not_to_be_visible()
    expect(page.get_by_text("Проверенные бесплатные ресурсы")).not_to_be_visible()


def test_season_detail_resources_visible_only_for_resource_goals(page: Page, live_server_url):
    _register_with_season(page, live_server_url, template_id="programming", sphere_id="career")
    page.set_viewport_size(VIEWPORT)
    page.goto(f"{live_server_url}/season")

    expect(page.get_by_text("Проверенные бесплатные ресурсы")).to_be_visible()
    expect(page.get_by_text("Лестница вызовов")).not_to_be_visible()
    expect(page.get_by_text("Банк вопросов для начала разговора")).not_to_be_visible()


# ---------------------------------------------------------------------------
# 6. /focus — дыхательный таймер (breathing_practice): техники + анимация
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("theme", THEMES)
def test_focus_breathing_screen(page: Page, live_server_url, theme):
    unique = _register_with_season(page, live_server_url, template_id="breathing_practice", sphere_id="energy")
    _force_day1_train(f"screens-{unique}", "breathing_practice")

    page.set_viewport_size(VIEWPORT)
    page.goto(f"{live_server_url}/focus")
    _set_theme(page, theme)

    expect(page.get_by_role("button", name="4–6 (медленное)")).to_be_visible()
    expect(page.get_by_role("button", name="Циклический вздох")).to_be_visible()
    _shoot(page, "focus-breathing-picker", theme)

    page.get_by_role("button", name="Циклический вздох").click()
    page.locator(".focus-duration-btn").first.click()
    expect(page.locator("#breathing-circle")).to_be_visible()
    expect(page.locator("#focus-clock")).to_be_visible()
    _shoot(page, "focus-breathing-running", theme)

    # happy path "быстрого" завершения: остановить до минуты -> на /today
    page.locator("#focus-stop").click()
    page.wait_for_url(f"{live_server_url}/today")


def test_focus_regular_timer_has_no_breathing_controls(page: Page, live_server_url):
    """Контраст с обычным /focus (deep_focus) — техник дыхания и кружка
    анимации у НЕ-дыхательной цели таймера быть не должно."""
    unique = _register_with_season(page, live_server_url, template_id="deep_focus", sphere_id="mind")

    with Session(engine) as db:
        user = db.exec(select(User).where(User.login == f"screens-{unique}")).first()
        season = db.exec(
            select(Season).where(Season.uid == user.id, Season.template_id == "deep_focus")
        ).first()
        day = db.exec(
            select(SeasonDay).where(SeasonDay.season_id == season.id, SeasonDay.day_number == 1)
        ).first()
        day.kind = "train"
        day.status = "planned"
        db.add(day)
        db.commit()

    page.set_viewport_size(VIEWPORT)
    page.goto(f"{live_server_url}/focus")

    expect(page.locator(".focus-duration-btn").first).to_be_visible()
    expect(page.locator("#breathing-circle")).to_have_count(0)
    expect(page.get_by_role("button", name="4–6 (медленное)")).to_have_count(0)
