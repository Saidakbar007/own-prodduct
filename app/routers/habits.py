"""
Привычки: создание, список, отметка за сегодня (антиобман), streak.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, Request
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.auth import require_user
from app.database import get_session
from app.models import Habit, HabitHistory, User
from app.services.points import award_points
from app.services.streak import calculate_streak

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _now() -> datetime:
    """Текущее время по UTC (с таймзоной) — именно его ставит сервер при отметке."""
    return datetime.now(timezone.utc)


def _habit_dates(db: Session, habit_id: int) -> set:
    """Все даты (без времени), когда привычка была отмечена."""
    history = db.exec(select(HabitHistory).where(HabitHistory.h_id == habit_id)).all()
    return {h.time.date() for h in history}


def habit_is_done_today(db: Session, habit_id: int) -> bool:
    """Отмечена ли привычка сегодня."""
    return _now().date() in _habit_dates(db, habit_id)


def _habits_context(db: Session, user: User, error: str = None) -> dict:
    """Собирает данные для шаблона habits.html: привычки + streak + статус за сегодня."""
    habits = db.exec(select(Habit).where(Habit.uid == user.id)).all()
    habits_with_info = []
    for habit in habits:
        dates = _habit_dates(db, habit.id)
        habits_with_info.append(
            {
                "habit": habit,
                "done_today": _now().date() in dates,
                "streak": calculate_streak(dates),
            }
        )
    return {"user": user, "habits": habits_with_info, "error": error}


@router.get("/habits")
def habits_list(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    """Список привычек пользователя с отметкой «сделано сегодня» и streak."""
    return templates.TemplateResponse(request, "habits.html", _habits_context(db, user))


@router.post("/habits")
def habit_create(
    request: Request,
    name: str = Form(...),
    description: str = Form(None),
    point: int = Form(10),
    story_point: float = Form(1.0),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """Создаёт новую привычку и обновляет счётчик привычек пользователя."""
    habit = Habit(uid=user.id, name=name, description=description, point=point, story_point=story_point)
    db.add(habit)

    user.habits += 1
    db.add(user)

    db.commit()
    return templates.TemplateResponse(request, "habits.html", _habits_context(db, user))


@router.post("/habits/{habit_id}/check")
def habit_check(
    habit_id: int,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """
    Отмечает привычку выполненной сегодня.
    Антиобман: время ставит сервер (_now()), отметить можно только
    один раз за сегодняшний день — клиент не может передать другую дату.
    """
    habit = db.get(Habit, habit_id)

    if not habit or habit.uid != user.id:
        return templates.TemplateResponse(
            request, "habits.html", _habits_context(db, user, "Привычка не найдена"), status_code=404
        )

    if habit_is_done_today(db, habit_id):
        return templates.TemplateResponse(
            request,
            "habits.html",
            _habits_context(db, user, "Эту привычку уже отметили сегодня"),
            status_code=400,
        )

    # Время ставит сервер, игнорируя всё, что мог бы прислать клиент
    entry = HabitHistory(h_id=habit_id, time=_now())
    db.add(entry)
    db.commit()

    award_points(db, user, int(habit.point * habit.story_point))

    return templates.TemplateResponse(request, "habits.html", _habits_context(db, user))
