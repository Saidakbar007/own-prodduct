"""
Точка входа в приложение.
Здесь создаётся объект FastAPI, подключаются шаблоны и роутеры.
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Request
from fastapi.exception_handlers import http_exception_handler as default_http_exception_handler
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from app import models  # noqa: F401 — импорт нужен, чтобы таблицы попали в metadata
from app.auth import get_current_user
from app.migrations_runner import run_migrations
from app.rendering import render
from app.routers import auth as auth_router
from app.routers import measure as measure_router
from app.routers import onboarding as onboarding_router
from app.routers import profile as profile_router
from app.routers import proofs as proofs_router
from app.routers import reveal as reveal_router
from app.routers import season as season_router
from app.routers import squad as squad_router
from app.routers import today as today_router

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """При старте сервера применяем миграции Alembic (создают/обновляют таблицы)."""
    run_migrations()
    yield


app = FastAPI(title="Сезоны", lifespan=lifespan)

# Подпись cookie-сессий секретным ключом из .env
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "dev-secret-key-change-me"),
)

# Дизайн-система (DESIGN.md) и 3D-арт — те же каталоги, что использует /design для показа
app.mount("/design", StaticFiles(directory="design"), name="design")
app.mount("/assets", StaticFiles(directory="assets"), name="assets")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth_router.router)
app.include_router(onboarding_router.router)
app.include_router(today_router.router)
app.include_router(season_router.router)
app.include_router(reveal_router.router)
app.include_router(measure_router.router)
app.include_router(squad_router.router)
app.include_router(profile_router.router)
app.include_router(proofs_router.router)


@app.exception_handler(StarletteHTTPException)
async def custom_404_handler(request: Request, exc: StarletteHTTPException):
    """Единообразная 404-страница; все остальные статусы — как обычно."""
    if exc.status_code != 404:
        return await default_http_exception_handler(request, exc)
    return render(request, "404.html", {}, status_code=404)


@app.get("/")
def index(request: Request, user=Depends(get_current_user)):
    """Гостю — приглашение начать сезон; вошедшему — сразу «Сегодня»."""
    if user:
        return RedirectResponse("/today", status_code=303)
    return render(request, "index.html", {"user": None, "lang": None})
