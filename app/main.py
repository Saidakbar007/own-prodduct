"""
Точка входа в приложение.
Здесь создаётся объект FastAPI, подключаются шаблоны и роутеры.
"""

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.database import create_db_and_tables
from app import models  # noqa: F401 — импорт нужен, чтобы таблицы попали в metadata

app = FastAPI(title="Моя жизнь (MVP)")

# Подключаем папку со статикой (картинки, css, если понадобятся)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Подключаем шаблоны Jinja2
templates = Jinja2Templates(directory="app/templates")


@app.on_event("startup")
def on_startup():
    """При старте сервера создаём таблицы в базе данных, если их ещё нет."""
    create_db_and_tables()


@app.get("/")
def index(request: Request):
    """Главная страница."""
    return templates.TemplateResponse(request, "index.html")
