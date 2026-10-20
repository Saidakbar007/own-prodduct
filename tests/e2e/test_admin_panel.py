"""
E2e админ-панели (v6d): собственный изолированный сервер (ADMIN_LOGINS
задан явно только для него) — чтобы не трогать общий demo-аккаунт из
tests/e2e/conftest.py, которым пользуются другие e2e-тесты (сид-данные
demo проверяются по конкретным числам, песочница их бы сломала).

Админ открывает галерею (все вкладки рендерятся, картинки грузятся),
применяет пресет "Легенда" -> /hero показывает стадию 5. Обычный
пользователь получает 404 на /admin.
"""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

PORT = 8730


def _free_port(port: int) -> int:
    for candidate in range(port, port + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", candidate)) != 0:
                return candidate
    return port


@pytest.fixture(scope="module")
def admin_server(tmp_path_factory):
    """Отдельный сервер с ADMIN_LOGINS=panel_admin — изолирован от общего e2e_server."""
    db_path = tmp_path_factory.mktemp("admin_e2e") / "admin_e2e.db"
    port = _free_port(PORT)
    base_url = f"http://127.0.0.1:{port}"

    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    env["SECRET_KEY"] = "e2e-admin-test-secret"
    env["ADMIN_LOGINS"] = "panel_admin"

    project_root = Path(__file__).resolve().parents[2]
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(project_root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    deadline = time.time() + 60
    ready = False
    while time.time() < deadline:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    ready = True
                    break
        except OSError:
            pass
        time.sleep(0.5)

    if not ready:
        proc.terminate()
        raise RuntimeError("Сервер для admin e2e-тестов не запустился за 60 секунд")

    time.sleep(1)
    yield base_url

    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def _register(page, base_url, login, password="secret123"):
    page.goto(f"{base_url}/register")
    page.fill('input[name="name"]', "Тест")
    page.fill('input[name="mail"]', f"{login}@example.com")
    page.fill('input[name="login"]', login)
    page.fill('input[name="password"]', password)
    page.fill('input[name="password_confirm"]', password)
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")


def test_admin_opens_gallery_all_tabs_render_with_images(page, admin_server):
    _register(page, admin_server, "panel_admin")

    page.set_viewport_size({"width": 1280, "height": 1000})
    page.goto(f"{admin_server}/admin/gallery")
    page.wait_for_load_state("networkidle")

    for tab_code in ("hero", "personas", "pets", "bosses", "bg", "frames", "titles", "effects", "badges", "season"):
        page.click(f"#gtab-{tab_code}")
        panel = page.locator(f"#gpanel-{tab_code}")
        assert "active" in (panel.get_attribute("class") or "")
        assert panel.locator("> div").count() > 0

    page.click("#gtab-hero")
    hero_img = page.locator("#gpanel-hero img").first
    assert hero_img.get_attribute("src")


def test_admin_applies_legend_preset_hero_shows_stage_five(page, admin_server):
    page.goto(f"{admin_server}/login")
    page.fill('input[name="login"]', "panel_admin")
    page.fill('input[name="password"]', "secret123")
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")

    page.goto(f"{admin_server}/admin/sandbox")
    page.wait_for_load_state("networkidle")

    page.click('form[action="/admin/sandbox/preset"] button:has-text("Легенда (ур. 50)")')
    page.wait_for_load_state("networkidle")

    page.goto(f"{admin_server}/hero")
    page.wait_for_load_state("networkidle")

    hero_img = page.locator('img[src*="hero_5"]').first
    assert hero_img.count() > 0


def test_regular_user_gets_404_on_admin(page, admin_server):
    _register(page, admin_server, "panel_regular")

    resp = page.goto(f"{admin_server}/admin")
    assert resp.status == 404
