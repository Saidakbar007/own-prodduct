"""
Всплывающие уведомления (toast) — очки, новый уровень, достижения.
Храним в cookie-сессии: добавили — на следующей отрисовке страницы показали и очистили.
"""

from fastapi import Request


def push_flash(request: Request, message: str, kind: str = "info") -> None:
    """Добавляет уведомление в очередь — покажется при следующей отрисовке страницы."""
    flashes = request.session.get("flashes", [])
    flashes.append({"message": message, "kind": kind})
    request.session["flashes"] = flashes


def pop_flashes(request: Request) -> list:
    """Забирает все накопленные уведомления и очищает очередь."""
    flashes = request.session.get("flashes", [])
    request.session["flashes"] = []
    return flashes
