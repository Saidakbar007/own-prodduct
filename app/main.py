"""
Точка входа в приложение.
Здесь создаётся объект FastAPI, подключаются шаблоны и роутеры.
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from datetime import date

from fastapi import Depends, FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from starlette.middleware.sessions import SessionMiddleware

from app.auth import get_current_user
from app.database import create_db_and_tables, get_session
from app import models  # noqa: F401 — импорт нужен, чтобы таблицы попали в metadata
from app.models import Goal, Level
from app.routers import auth as auth_router
from app.routers import profile as profile_router
from app.routers import habits as habits_router
from app.routers import goals as goals_router
from app.routers import stats as stats_router
from app.routers import programs as programs_router
from app.routers import friends as friends_router
from app.routers import coach as coach_router
from app.routers.habits import _habits_context

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
app.include_router(habits_router.router)
app.include_router(goals_router.router)
app.include_router(stats_router.router)
app.include_router(programs_router.router)
app.include_router(friends_router.router)
app.include_router(coach_router.router)


@app.get("/")
def index(request: Request, user=Depends(get_current_user), db: Session = Depends(get_session)):
    """
    Главная страница.
    Гостю показывает приглашение зарегистрироваться.
    Вошедшему — дашборд: сегодняшние привычки, уровень и ближайшие дедлайны.
    """
    if not user:
        return templates.TemplateResponse(request, "index.html", {"user": None})

    habits_context = _habits_context(db, user)
    level = db.exec(select(Level).where(Level.uid == user.id)).first()

    deadlines = db.exec(
        select(Goal)
        .where(Goal.uid == user.id, Goal.status != "completed", Goal.deadline != None)  # noqa: E711
        .order_by(Goal.deadline.asc())
        .limit(5)
    ).all()

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "user": user,
            "habits": habits_context["habits"],
            "level": level,
            "deadlines": deadlines,
            "today": date.today(),
        },
    )
