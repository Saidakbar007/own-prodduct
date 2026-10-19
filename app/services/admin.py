"""
Доступ к админке (v6d): только логины из переменной окружения ADMIN_LOGINS
(через запятую). Остальным /admin — 404 (не 403 — чтобы не выдавать, что
раздел вообще существует).
"""

import os

from app.models import User


def admin_logins() -> set[str]:
    raw = os.getenv("ADMIN_LOGINS", "")
    return {login.strip() for login in raw.split(",") if login.strip()}


def is_admin(user: User | None) -> bool:
    if not user:
        return False
    return user.login in admin_logins()
