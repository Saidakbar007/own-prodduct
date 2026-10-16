"""
Точка входа в приложение.
Здесь создаётся объект FastAPI, подключаются шаблоны и роутеры.
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.auth import get_current_user
from app.database import create_db_and_tables
from app import models  # noqa: F401 — импорт нужен, чтобы таблицы попали в metadata
from app.routers import auth as auth_router
from app.routers import profile as profile_router

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """При старте сервера создаём таблицы в базе данных, если их ещё нет."""
    create_db_and_tables()
    yield


app = FastAPI(title="Моя жизнь (MVP)", lifespan=lifespan)

# Подпись cookie-сессий секретным ключом из .env
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "dev-secret-key-change-me"),
)

# Подключаем папку со статикой (картинки, css, если понадобятся)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Подключаем шаблоны Jinja2
templates = Jinja2Templates(directory="app/templates")

# Роуты регистрации/входа/выхода
app.include_router(auth_router.router)
app.include_router(profile_router.router)


@app.get("/")
def index(request: Request, user=Depends(get_current_user)):
    """Главная страница. Показывает разный контент вошедшим и гостям."""
    return templates.TemplateResponse(request, "index.html", {"user": user})
