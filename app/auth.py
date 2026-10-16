"""
Всё, что связано с авторизацией:
- хеширование и проверка пароля
- получение текущего пользователя из сессии (cookie)
"""

from typing import Optional

from fastapi import Depends, HTTPException, Request
from passlib.context import CryptContext
from sqlmodel import Session

from app.database import get_session
from app.models import User

# Контекст passlib для хеширования паролей через bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Превращает пароль в хеш для хранения в базе."""
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Проверяет, что введённый пароль совпадает с хешем из базы."""
    return pwd_context.verify(password, password_hash)


def get_current_user(request: Request, db: Session = Depends(get_session)) -> Optional[User]:
    """
    Достаёт текущего пользователя из cookie-сессии.
    Если пользователь не вошёл в систему — возвращает None.
    """
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.get(User, user_id)


def require_user(request: Request, db: Session = Depends(get_session)) -> User:
    """
    Зависимость для защищённых страниц.
    Если пользователь не вошёл — редиректит на /login (303 See Other).
    """
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return user
