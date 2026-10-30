"""
Всё, что связано с авторизацией:
- хеширование и проверка пароля
- получение текущего пользователя из cookie-сессии
"""

import os
from typing import Optional

from fastapi import Depends, HTTPException, Request
from passlib.context import CryptContext
from sqlmodel import Session

from app.database import get_session
from app.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Превращает пароль в хеш для хранения в базе."""
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Проверяет, что введённый пароль совпадает с хешем из базы."""
    return pwd_context.verify(password, password_hash)


def get_current_user(request: Request, db: Session = Depends(get_session)) -> Optional[User]:
    """Достаёт текущего пользователя из cookie-сессии (или None, если гость)."""
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.get(User, user_id)


def require_user(request: Request, db: Session = Depends(get_session)) -> User:
    """Зависимость для защищённых страниц: редирект на /login, если не вошёл."""
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return user


def is_admin(user: Optional[User]) -> bool:
    """§14: доступ по ADMIN_LOGINS (через запятую). Без переменной — админов нет."""
    if not user:
        return False
    logins = {login.strip() for login in os.getenv("ADMIN_LOGINS", "").split(",") if login.strip()}
    return user.login in logins


def require_admin(request: Request, db: Session = Depends(get_session)) -> User:
    """Зависимость для /admin/*: 404 (не 403 — не выдаём, что раздел вообще
    есть), если не вошёл или не в ADMIN_LOGINS."""
    user = get_current_user(request, db)
    if not user or not is_admin(user):
        raise HTTPException(status_code=404)
    return user
