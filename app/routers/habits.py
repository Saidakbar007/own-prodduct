"""
Привычки: создание, список, отметка за сегодня (антиобман), streak с заморозкой,
тип (полезная/вредная), частота, календарь за 30 дней, честные пропуски,
минимальная версия "на плохой день", фото-доказательство.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlmodel import Session, select

from app.auth import require_user
from app.database import get_session
from app.models import Bet, BonusFreeze, Habit, HabitHistory, Partnership, User
from app.rendering import render
from app.services.achievements import check_and_award_achievements
from app.services.adaptive_plan import adaptive_plan_message, apply_adaptive_plan, needs_adaptive_plan
from app.services.bets import evaluate_bets_for_habit
from app.services.chests import maybe_award_chest
from app.services.flash import push_flash
from app.services.partnerships import combined_streak, evaluate_partnerships_for_habit
from app.services.points import points_for_habit_difficulty, award_points
from app.services.streak import calculate_streak, calculate_streak_with_freeze
from app.services.trust import refresh_trust_score
from app.services.uploads import save_proof_photo

router = APIRouter()

WEEKDAY_LABELS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
MINIMAL_POINTS_DIVISOR = 2
SKIP_HONESTY_POINTS = 2


def _now() -> datetime:
    """Текущее время по UTC (с таймзоной) — именно его ставит сервер при отметке."""
    return datetime.now(timezone.utc)


def _habit_entries(db: Session, habit_id: int) -> list[HabitHistory]:
    return db.exec(select(HabitHistory).where(HabitHistory.h_id == habit_id)).all()


def _habit_dates(db: Session, habit_id: int, kinds: tuple = None) -> set:
    """Даты (без времени) отметок привычки, опционально только нужных видов (kind)."""
    entries = _habit_entries(db, habit_id)
    if kinds:
        entries = [e for e in entries if e.kind in kinds]
    return {e.time.date() for e in entries}


def _bonus_freezes_for(db: Session, uid: int) -> dict:
    rows = db.exec(select(BonusFreeze).where(BonusFreeze.uid == uid)).all()
    return {r.week_key: r.amount for r in rows}


def habit_logged_today(db: Session, habit_id: int) -> bool:
    """Есть ли сегодня хоть какая-то отметка (done/minimal/skip)."""
    return _now().date() in _habit_dates(db, habit_id)


def habit_due_today(habit: Habit) -> bool:
    """Запланирована ли привычка на сегодня (для daily — всегда да)."""
    if habit.frequency != "weekly" or not habit.weekdays:
        return True
    today_weekday = str(_now().weekday())
    return today_weekday in habit.weekdays.split(",")


def habits_at_risk(db: Session, user: User) -> list[Habit]:
    """
    Привычки, которые вчера пропустили полностью (без единой отметки) —
    для мягкого экрана возврата ("не пропускай дважды").
    """
    yesterday = _now().date() - timedelta(days=1)
    habits = db.exec(select(Habit).where(Habit.uid == user.id)).all()
    at_risk = []
    for habit in habits:
        if not habit_due_today(habit):
            continue
        if habit_logged_today(db, habit.id):
            continue
        dates = _habit_dates(db, habit.id)
        if yesterday not in dates:
            at_risk.append(habit)
    return at_risk


def _habits_context(db: Session, user: User, error: str = None) -> dict:
    """Собирает данные для шаблона habits.html: привычки + streak + статус за сегодня."""
    habits = db.exec(select(Habit).where(Habit.uid == user.id)).all()
    bonus_freezes = _bonus_freezes_for(db, user.id)
    habits_with_info = []
    for habit in habits:
        done_dates = _habit_dates(db, habit.id, kinds=("done", "minimal"))
        skip_dates = _habit_dates(db, habit.id, kinds=("skip",))
        streak_info = calculate_streak_with_freeze(done_dates, skip_dates, bonus_freezes)
        habits_with_info.append(
            {
                "habit": habit,
                "done_today": _now().date() in done_dates,
                "streak": streak_info["streak"],
                "freezes_left": streak_info["freezes_left"],
                "due_today": habit_due_today(habit),
            }
        )
    return {"user": user, "habits": habits_with_info, "error": error}


@router.get("/habits")
def habits_list(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    """Список привычек пользователя с отметкой «сделано сегодня», streak и заморозками."""
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
    requires_proof: Optional[str] = Form(None),
    minimal_description: str = Form(None),
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
        requires_proof=bool(requires_proof),
        minimal_description=minimal_description,
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
    """Страница одной привычки: календарь за 30 дней, streak+заморозка, напарник, ставки, сундуки."""
    habit = db.get(Habit, habit_id)
    if not habit or habit.uid != user.id:
        return render(
            request, "habits.html", _habits_context(db, user, "Привычка не найдена"), db=db, user=user, status_code=404
        )

    done_dates = _habit_dates(db, habit_id, kinds=("done", "minimal"))
    skip_dates = _habit_dates(db, habit_id, kinds=("skip",))
    all_dates = done_dates | skip_dates
    today = _now().date()

    days = []
    for i in range(29, -1, -1):
        day = today - timedelta(days=i)
        kind = "done" if day in done_dates else ("skip" if day in skip_dates else None)
        days.append({"date": day, "kind": kind})

    bonus_freezes = _bonus_freezes_for(db, user.id)
    streak_info = calculate_streak_with_freeze(done_dates, skip_dates, bonus_freezes)

    active_bet = db.exec(
        select(Bet).where(Bet.habit_id == habit_id, Bet.status == "active")
    ).first()
    past_bets = db.exec(
        select(Bet).where(Bet.habit_id == habit_id, Bet.status != "active")
    ).all()

    partnership = db.exec(
        select(Partnership).where(
            (Partnership.habit_id_a == habit_id) | (Partnership.habit_id_b == habit_id)
        )
    ).first()
    partner_streak = combined_streak(db, partnership) if partnership and partnership.status == "active" else None

    adaptive_suggestion = adaptive_plan_message(habit) if needs_adaptive_plan(db, habit) else None

    return render(
        request,
        "habit_detail.html",
        {
            "user": user,
            "habit": habit,
            "days": days,
            "done_today": today in done_dates,
            "logged_today": today in all_dates,
            "streak": streak_info["streak"],
            "freezes_left": streak_info["freezes_left"],
            "active_bet": active_bet,
            "past_bets": past_bets,
            "partnership": partnership,
            "partner_streak": partner_streak,
            "adaptive_suggestion": adaptive_suggestion,
        },
        db=db,
        user=user,
    )


@router.post("/habits/{habit_id}/adaptive-plan/apply")
def apply_adaptive_plan_route(
    habit_id: int,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """Применяет урезанный план одним кликом (daily -> 3 дня в неделю)."""
    habit = db.get(Habit, habit_id)
    if habit and habit.uid == user.id:
        apply_adaptive_plan(db, habit)
        push_flash(request, "План урезан до 3 дней в неделю — серию это не прервёт 💛")

    return habit_detail(habit_id, request, user, db)


@router.post("/habits/{habit_id}/check")
async def habit_check(
    habit_id: int,
    request: Request,
    kind: str = Form("done"),
    proof: Optional[UploadFile] = File(None),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """
    Отмечает привычку: done (полностью) / minimal (на плохой день) / skip (честный пропуск).
    Антиобман: время ставит сервер, отметить можно только один раз за сегодняшний день.
    """
    habit = db.get(Habit, habit_id)

    if not habit or habit.uid != user.id:
        return render(
            request, "habits.html", _habits_context(db, user, "Привычка не найдена"), db=db, user=user, status_code=404
        )

    if habit_logged_today(db, habit_id):
        return render(
            request,
            "habits.html",
            _habits_context(db, user, "Эту привычку уже отметили сегодня"),
            db=db,
            user=user,
            status_code=400,
        )

    if kind not in ("done", "minimal", "skip"):
        kind = "done"

    proof_path = None
    if kind in ("done", "minimal"):
        if proof is not None and proof.filename:
            proof_path = save_proof_photo(proof)
        elif habit.requires_proof:
            return render(
                request,
                "habits.html",
                _habits_context(db, user, "Для этой привычки нужно фото-доказательство"),
                db=db,
                user=user,
                status_code=400,
            )

    # Время ставит сервер, игнорируя всё, что мог бы прислать клиент
    entry = HabitHistory(h_id=habit_id, time=_now(), kind=kind, proof_path=proof_path)
    db.add(entry)
    db.commit()

    if kind == "skip":
        level, leveled_up = award_points(db, user, SKIP_HONESTY_POINTS)
        push_flash(request, f"Честно признано 🙏 +{SKIP_HONESTY_POINTS} очка за честность")
    else:
        base_points = habit.point if kind == "done" else max(1, habit.point // MINIMAL_POINTS_DIVISOR)
        level, leveled_up = award_points(db, user, base_points)
        push_flash(request, f"+{base_points} очков 🎉")

    if leveled_up:
        push_flash(request, f"⭐ Новый уровень: «{level.name}»!", "level-up")

    refresh_trust_score(db, user)
    evaluate_bets_for_habit(db, habit_id)
    evaluate_partnerships_for_habit(db, habit_id)

    chest = maybe_award_chest(db, user, habit)
    if chest:
        push_flash(request, f"🎁 Сундук за неделю без пропусков: {chest.reward_value}!", "chest")

    newly_earned = check_and_award_achievements(db, user)
    for achievement in newly_earned:
        push_flash(request, f"{achievement.icon} Новое достижение: «{achievement.name}»!", "achievement")

    return render(request, "habits.html", _habits_context(db, user), db=db, user=user)
