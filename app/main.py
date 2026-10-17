"""
Точка входа в приложение.
Здесь создаётся объект FastAPI, подключаются шаблоны и роутеры.
"""

import os
from contextlib import asynccontextmanager
from datetime import date

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Request
from fastapi.exception_handlers import http_exception_handler as default_http_exception_handler
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from app.auth import get_current_user
from app.database import engine, get_session
from app import models  # noqa: F401 — импорт нужен, чтобы таблицы попали в metadata
from app.migrations_runner import run_migrations
from app.models import Goal, Level, User, UserAchievement, Achievement
from app.rendering import render
from app.routers import auth as auth_router
from app.routers import profile as profile_router
from app.routers import habits as habits_router
from app.routers import goals as goals_router
from app.routers import stats as stats_router
from app.routers import programs as programs_router
from app.routers import friends as friends_router
from app.routers import coach as coach_router
from app.routers import achievements as achievements_router
from app.routers import daily_tasks as daily_tasks_router
from app.routers import confirmations as confirmations_router
from app.routers import bets as bets_router
from app.routers import partnerships as partnerships_router
from app.routers import onboarding as onboarding_router
from app.routers import game_assets as game_assets_router
from app.routers import hero as hero_router
from app.routers import shop as shop_router
from app.routers.habits import _habits_context, habits_at_risk
from app.services.achievements import ensure_achievements_seeded
from app.services.shop import ensure_shop_seeded
from app.services.daily_tasks import get_or_create_today_tasks
from app.services.pentagon import pentagon_chart
from app.services.spheres import all_spheres_progress
from app.services.progress import dream_progress_percent

load_dotenv()

os.makedirs("uploads", exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    При старте сервера: применяем миграции Alembic (создают/обновляют таблицы),
    заполняем каталог достижений, и если база пустая — запускаем seed автоматически.
    """
    run_migrations()
    with Session(engine) as db:
        ensure_achievements_seeded(db)
        ensure_shop_seeded(db)

        from app.models import Registration

        if not db.exec(select(Registration)).first():
            import seed

            seed.main()

    yield


app = FastAPI(title="Моя жизнь (MVP)", lifespan=lifespan)

# Подпись cookie-сессий секретным ключом из .env
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "dev-secret-key-change-me"),
)

# Статика и загруженные фото-доказательства
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Роуты
app.include_router(auth_router.router)
app.include_router(profile_router.router)
app.include_router(habits_router.router)
app.include_router(goals_router.router)
app.include_router(stats_router.router)
app.include_router(programs_router.router)
app.include_router(friends_router.router)
app.include_router(coach_router.router)
app.include_router(achievements_router.router)
app.include_router(daily_tasks_router.router)
app.include_router(confirmations_router.router)
app.include_router(bets_router.router)
app.include_router(partnerships_router.router)
app.include_router(onboarding_router.router)
app.include_router(game_assets_router.router)
app.include_router(hero_router.router)
app.include_router(shop_router.router)


@app.exception_handler(StarletteHTTPException)
async def custom_404_handler(request: Request, exc: StarletteHTTPException):
    """Красивая 404-страница для несуществующих адресов; все остальные статусы — как обычно."""
    if exc.status_code != 404:
        return await default_http_exception_handler(request, exc)

    user = None
    user_id = request.session.get("user_id")
    if user_id:
        with Session(engine) as db:
            user = db.get(User, user_id)

    return render(request, "404.html", {"user": user}, status_code=404)


@app.get("/")
def index(request: Request, user=Depends(get_current_user), db: Session = Depends(get_session)):
    """
    Главная страница.
    Гостю показывает приглашение зарегистрироваться.
    Вошедшему — дашборд: сегодняшние привычки, уровень, ежедневное задание,
    ближайшие дедлайны, последнее достижение, прогресс к мечте и мягкий
    экран возврата для пропущенных вчера привычек.
    """
    if not user:
        return render(request, "index.html", {"user": None})

    habits_context = _habits_context(db, user)
    level = db.exec(select(Level).where(Level.uid == user.id)).first()

    deadlines = db.exec(
        select(Goal)
        .where(Goal.uid == user.id, Goal.status != "completed", Goal.deadline != None)  # noqa: E711
        .order_by(Goal.deadline.asc())
        .limit(5)
    ).all()

    daily_tasks = get_or_create_today_tasks(db, user)

    last_user_achievement = db.exec(
        select(UserAchievement)
        .where(UserAchievement.uid == user.id)
        .order_by(UserAchievement.earned_date.desc())
    ).first()
    last_achievement = None
    if last_user_achievement:
        last_achievement = db.get(Achievement, last_user_achievement.achievement_id)

    top_dream = db.exec(select(Goal).where(Goal.uid == user.id, Goal.parent_id == None)).first()  # noqa: E711
    dream_progress = dream_progress_percent(db, top_dream) if top_dream else None

    return render(
        request,
        "index.html",
        {
            "user": user,
            "habits": habits_context["habits"],
            "level": level,
            "deadlines": deadlines,
            "daily_tasks": daily_tasks,
            "last_achievement": last_achievement,
            "top_dream": top_dream,
            "dream_progress": dream_progress,
            "at_risk_habits": habits_at_risk(db, user),
            "today": date.today(),
            "hero_chart": pentagon_chart(all_spheres_progress(db, user.id)),
        },
        db=db,
        user=user,
    )
