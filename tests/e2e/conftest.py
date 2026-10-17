"""
Инфраструктура e2e-тестов: поднимает настоящий uvicorn-сервер на отдельном
порту с изолированной БД (DATABASE_URL на временный файл) и засеивает
демо-пользователя — Playwright кликает по реальным страницам, не через
TestClient.
"""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

PORT = 8711
BASE_URL = f"http://127.0.0.1:{PORT}"


def _free_port(port: int) -> int:
    """Если порт занят — берёт следующий свободный (на случай параллельных прогонов)."""
    for candidate in range(port, port + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", candidate)) != 0:
                return candidate
    return port


@pytest.fixture(scope="session")
def e2e_server(tmp_path_factory):
    """Запускает реальный сервер приложения для всей e2e-сессии."""
    db_path = tmp_path_factory.mktemp("e2e") / "e2e.db"
    port = _free_port(PORT)
    base_url = f"http://127.0.0.1:{port}"

    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    env["SECRET_KEY"] = "e2e-test-secret"

    project_root = Path(__file__).resolve().parents[2]
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(project_root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    # Ждём, пока сервер поднимется (миграции + seed при первом старте)
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
        raise RuntimeError("Сервер для e2e-тестов не запустился за 60 секунд")

    time.sleep(1)  # дать seed/migrations спокойно завершиться после открытия порта

    yield base_url

    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture
def demo_page(page, e2e_server):
    """Открытая страница, уже залогиненная под demo (через /try-demo)."""
    page.goto(f"{e2e_server}/try-demo")
    page.wait_for_load_state("networkidle")
    return page
