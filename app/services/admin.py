"""
Доступ к админке (v6d): только логины из переменной окружения ADMIN_LOGINS
(через запятую). Остальным /admin — 404 (не 403 — чтобы не выдавать, что
раздел вообще существует).

Если ADMIN_LOGINS не задан локально — demo становится админом по умолчанию,
чтобы сразу видеть /admin после `python seed.py`. На Render это не
срабатывает: платформа сама выставляет RENDER=true всем сервисам, и этот
дефолт там отключён — там ADMIN_LOGINS обязателен (см. render.yaml, sync: false).
"""

import os

from app.models import User

DEV_DEFAULT_ADMIN = "demo"


def admin_logins() -> set[str]:
    raw = os.getenv("ADMIN_LOGINS", "")
    logins = {login.strip() for login in raw.split(",") if login.strip()}
    if not logins and not os.getenv("RENDER"):
        return {DEV_DEFAULT_ADMIN}
    return logins


def is_admin(user: User | None) -> bool:
    if not user:
        return False
    return user.login in admin_logins()
