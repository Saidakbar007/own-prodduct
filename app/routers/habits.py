"""
Привычки: создание, список, отметка за сегодня (антиобман), streak,
тип (полезная/вредная), частота (каждый день / дни недели), календарь за 30 дней.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Form, Request
from sqlmodel import Session, select

from app.auth import require_user
from app.database import get_session
from app.models import Habit, HabitHistory, User
from app.rendering import render
from app.services.achievements import check_and_award_achievements
from app.services.flash import push_flash
from app.services.points import points_for_habit_difficulty, award_points
from app.services.streak import calculate_streak

router = APIRouter()

WEEKDAY_LABELS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


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


def habit_due_today(habit: Habit) -> bool:
    """Запланирована ли привычка на сегодня (для daily — всегда да)."""
    if habit.frequency != "weekly" or not habit.weekdays:
        return True
    today_weekday = str(_now().weekday())
    return today_weekday in habit.weekdays.split(",")


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
                "due_today": habit_due_today(habit),
            }
        )
    return {"user": user, "habits": habits_with_info, "error": error}


@router.get("/habits")
def habits_list(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    """Список привычек пользователя с отметкой «сделано сегодня» и streak."""
    return render(request, "habits.html", _habits_context(db, user), db=db, user=user)


@router.post("/habits")
def habit_create(
    request: Request,
    name: str = Form(...),
    description: str = Form(None),
    difficulty: str = Form("medium"),
    habit_type: str = Form("useful"),
    frequency: str = Form("daily"),
    weekdays: Optional[List[str]] = Form(None),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """Создаёт новую привычку. Очки считает сервер по сложности, клиент их не присылает."""
    habit = Habit(
        uid=user.id,
        name=name,
        description=description,
        point=points_for_habit_difficulty(difficulty),
        story_point=1.0,
        habit_type=habit_type,
        frequency=frequency,
        weekdays=",".join(weekdays) if frequency == "weekly" and weekdays else None,
    )
    db.add(habit)

    user.habits += 1
    db.add(user)

    db.commit()

    newly_earned = check_and_award_achievements(db, user)
    for achievement in newly_earned:
        push_flash(request, f"{achievement.icon} Новое достижение: «{achievement.name}»!", "achievement")

    return render(request, "habits.html", _habits_context(db, user), db=db, user=user)


@router.get("/habits/{habit_id}")
def habit_detail(
    habit_id: int,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """Страница одной привычки: календарь-сетка выполнения за 30 дней."""
    habit = db.get(Habit, habit_id)
    if not habit or habit.uid != user.id:
        return render(
            request, "habits.html", _habits_context(db, user, "Привычка не найдена"), db=db, user=user, status_code=404
        )

    dates = _habit_dates(db, habit_id)
    today = _now().date()
    days = []
    for i in range(29, -1, -1):
        day = today - timedelta(days=i)
        days.append({"date": day, "done": day in dates})

    return render(
        request,
        "habit_detail.html",
        {
            "user": user,
            "habit": habit,
            "days": days,
            "done_today": today in dates,
            "streak": calculate_streak(dates),
        },
        db=db,
        user=user,
    )


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
        return render(
            request, "habits.html", _habits_context(db, user, "Привычка не найдена"), db=db, user=user, status_code=404
        )

    if habit_is_done_today(db, habit_id):
        return render(
            request,
            "habits.html",
            _habits_context(db, user, "Эту привычку уже отметили сегодня"),
            db=db,
            user=user,
            status_code=400,
        )

    # Время ставит сервер, игнорируя всё, что мог бы прислать клиент
    entry = HabitHistory(h_id=habit_id, time=_now())
    db.add(entry)
    db.commit()

    points = int(habit.point * habit.story_point)
    level, leveled_up = award_points(db, user, points)
    push_flash(request, f"+{points} очков 🎉")
    if leveled_up:
        push_flash(request, f"⭐ Новый уровень: «{level.name}»!", "level-up")

    newly_earned = check_and_award_achievements(db, user)
    for achievement in newly_earned:
        push_flash(request, f"{achievement.icon} Новое достижение: «{achievement.name}»!", "achievement")

    return render(request, "habits.html", _habits_context(db, user), db=db, user=user)
