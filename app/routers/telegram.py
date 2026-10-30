"""
Telegram (§12 ТЗ, Фаза 3): Mini App (initData + HMAC) и webhook бота —
оба на этом же сервисе Render. Без токена бота остальное приложение
работает (is_configured() == False просто отключает эти роуты по сути).
"""

import os

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.auth import hash_password, verify_password
from app.database import get_session
from app.models import User
from app.rendering import render
from app.services.telegram_auth import telegram_user_from_init_data, verify_init_data
from app.services.telegram_bot import handle_update

router = APIRouter()


def _bot_token() -> str:
    return os.getenv("TELEGRAM_BOT_TOKEN", "")


@router.post("/telegram/auth")
def telegram_auth(request: Request, init_data: str = Form(...), db: Session = Depends(get_session)):
    bot_token = _bot_token()
    if not bot_token:
        raise HTTPException(status_code=503, detail="Telegram не настроен")

    verified = verify_init_data(init_data, bot_token)
    if not verified:
        raise HTTPException(status_code=401, detail="Подпись initData неверна")

    tg_user = telegram_user_from_init_data(verified)
    if not tg_user or "id" not in tg_user:
        raise HTTPException(status_code=400, detail="Нет данных пользователя")

    tg_id = tg_user["id"]
    user = db.exec(select(User).where(User.telegram_user_id == tg_id)).first()
    if user:
        request.session["user_id"] = user.id
        return RedirectResponse("/today", status_code=303)

    request.session["telegram_pending_id"] = tg_id
    request.session["telegram_pending_name"] = tg_user.get("first_name", "")
    return RedirectResponse("/telegram/link", status_code=303)


@router.get("/telegram/link")
def link_page(request: Request):
    if "telegram_pending_id" not in request.session:
        return RedirectResponse("/", status_code=303)
    return render(request, "telegram_link.html", {"error": None, "lang": None})


@router.post("/telegram/link/existing")
def link_existing(
    request: Request,
    login: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_session),
):
    tg_id = request.session.get("telegram_pending_id")
    if not tg_id:
        return RedirectResponse("/", status_code=303)

    user = db.exec(select(User).where(User.login == login)).first()
    if not user or not verify_password(password, user.password_hash):
        return render(request, "telegram_link.html", {"error": "auth.error_invalid_credentials", "lang": None})

    user.telegram_user_id = tg_id
    db.add(user)
    db.commit()

    request.session.pop("telegram_pending_id", None)
    request.session.pop("telegram_pending_name", None)
    request.session["user_id"] = user.id
    return RedirectResponse("/today", status_code=303)


@router.post("/telegram/webhook")
async def webhook(request: Request, db: Session = Depends(get_session)):
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    expected = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
    if not expected or secret != expected:
        raise HTTPException(status_code=401)

    update = await request.json()
    handle_update(db, update)
    return {"ok": True}
