"""
Точка входа в приложение.
Здесь создаётся объект FastAPI, подключаются шаблоны и роутеры.
"""

import asyncio
import contextlib
import logging
import os
from contextlib import asynccontextmanager

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Request
from fastapi.exception_handlers import http_exception_handler as default_http_exception_handler
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, text
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from app import models  # noqa: F401 — импорт нужен, чтобы таблицы попали в metadata
from app.auth import get_current_user
from app.database import engine, get_session
from app.migrations_runner import run_migrations
from app.rendering import render
from app.routers import admin as admin_router
from app.routers import auth as auth_router
from app.routers import challenge as challenge_router
from app.routers import focus as focus_router
from app.routers import habits as habits_router
from app.routers import measure as measure_router
from app.routers import onboarding as onboarding_router
from app.routers import profile as profile_router
from app.routers import proofs as proofs_router
from app.routers import reveal as reveal_router
from app.routers import season as season_router
from app.routers import squad as squad_router
from app.routers import telegram as telegram_router
from app.routers import today as today_router
from app.routers import expenses as expenses_router
from app.routers import week as week_router
from app.routers import workout as workout_router
from app.services.telegram_api import is_configured as telegram_is_configured
from app.services.telegram_bot import run_due_reminders

load_dotenv()

REMINDER_INTERVAL_SECONDS = 60
SELF_PING_INTERVAL_SECONDS = 600


async def _self_ping_loop() -> None:
    """«Доделай»: Render free — засыпает без входящего трафика 15+ минут.
    Самопинг каждые 10 минут на собственный /healthz (внешний URL из
    RENDER_EXTERNAL_URL, который Render подставляет сам) — это настоящий
    входящий HTTP-запрос к сервису, он и не даёт инстансу уснуть. Не
    заменяет перевод на платный тариф (см. "Напомни мне в конце" в
    START_1.0.md) — это бесплатный костыль на время, пока тариф не оплачен."""
    base_url = os.getenv("RENDER_EXTERNAL_URL")
    if not base_url:
        return
    async with httpx.AsyncClient(timeout=10) as client:
        while True:
            try:
                await client.get(f"{base_url.rstrip('/')}/healthz")
            except Exception:
                logging.getLogger("sezony.selfping").exception("self-ping failed")
            await asyncio.sleep(SELF_PING_INTERVAL_SECONDS)


async def _reminder_loop() -> None:
    """Напоминания бота (§12) — без отдельного cron: тот же процесс веб-
    сервиса, фоновый цикл раз в минуту. При нескольких инстансах Render
    напоминания задублируются — пока единственный инстанс, это не проблема
    (см. docs/decisions/DECISIONS.md)."""
    while True:
        try:
            if telegram_is_configured():
                with Session(engine) as db:
                    run_due_reminders(db)
        except Exception:
            logging.getLogger("sezony.telegram").exception("reminder loop failed")
        await asyncio.sleep(REMINDER_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """При старте сервера применяем миграции Alembic и запускаем фоновый
    цикл напоминаний бота."""
    run_migrations()
    reminder_task = asyncio.create_task(_reminder_loop())
    self_ping_task = asyncio.create_task(_self_ping_loop())
    try:
        yield
    finally:
        reminder_task.cancel()
        self_ping_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await reminder_task
        with contextlib.suppress(asyncio.CancelledError):
            await self_ping_task


app = FastAPI(title="NewLife", lifespan=lifespan)

# Подпись cookie-сессий секретным ключом из .env
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "dev-secret-key-change-me"),
)

# Дизайн-система (docs/design/DESIGN.md) и 3D-арт — те же каталоги, что использует /design для показа
app.mount("/design", StaticFiles(directory="design", html=True), name="design")
app.mount("/assets", StaticFiles(directory="assets"), name="assets")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth_router.router)
app.include_router(onboarding_router.router)
app.include_router(today_router.router)
app.include_router(season_router.router)
app.include_router(reveal_router.router)
app.include_router(measure_router.router)
app.include_router(focus_router.router)
app.include_router(challenge_router.router)
app.include_router(squad_router.router)
app.include_router(profile_router.router)
app.include_router(proofs_router.router)
app.include_router(telegram_router.router)
app.include_router(week_router.router)
app.include_router(habits_router.router)
app.include_router(workout_router.router)
app.include_router(expenses_router.router)
app.include_router(admin_router.router)


@app.exception_handler(StarletteHTTPException)
async def custom_404_handler(request: Request, exc: StarletteHTTPException):
    """Единообразная 404-страница; все остальные статусы — как обычно."""
    if exc.status_code != 404:
        return await default_http_exception_handler(request, exc)
    return render(request, "404.html", {}, status_code=404)


@app.get("/healthz")
def healthz(db: Session = Depends(get_session)):
    """Для Render health-check и самопинга (_self_ping_loop). Без авторизации
    (мониторингу не нужен логин) — но реально проверяет БД, а не просто
    отвечает 200 вхолостую."""
    db.exec(text("SELECT 1"))
    return JSONResponse({"status": "ok"})


@app.get("/")
def index(request: Request, user=Depends(get_current_user)):
    """Гостю — приглашение начать сезон; вошедшему — сразу «Сегодня»."""
    if user:
        return RedirectResponse("/today", status_code=303)
    return render(request, "index.html", {"user": None, "lang": None})
