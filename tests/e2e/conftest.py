"""
Поднимает приложение (с той же временной БД, что и обычные тесты —
см. tests/conftest.py) на свободном порту, чтобы Playwright мог открыть
его в настоящем браузере.
"""

import contextlib
import socket
import threading
import time

import pytest
import uvicorn

from app.main import app


def _free_port() -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def live_server_url():
    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    for _ in range(200):
        if server.started:
            break
        time.sleep(0.05)
    else:
        raise RuntimeError("Тестовый сервер не поднялся за отведённое время")

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join(timeout=5)
