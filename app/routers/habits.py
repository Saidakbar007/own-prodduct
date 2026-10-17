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
from app.services.catalog import CATALOG, find_by_code
from app.services.chests import maybe_award_chest
from app.services.coins import HABIT_COINS, PROOF_PHOTO_BONUS, award_coins
from app.services.difficulty import calculate_difficulty, clamp_difficulty, difficulty_from_points
from app.services.flash import push_flash
from app.services.levels import level_for_xp, level_up_message
from app.services.partnerships import combined_streak, evaluate_partnerships_for_habit
from app.services.personas import WAKING_XP_BONUS, is_waking
from app.services.persona_voices import is_streak_milestone, skip_line, streak_line
from app.services.points import points_for_habit_difficulty, award_points
from app.services.recalibration import maybe_recalibrate
from app.services.shop import use_freeze
from app.services.spheres import SPHERES, log_sphere_xp
from app.services.streak import calculate_streak_with_freeze
from app.services.trust import refresh_trust_score
from app.services.uploads import save_proof_photo
from app.services.usertime import local_date, today_for

router = APIRouter()

WEEKDAY_LABELS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
MINIMAL_POINTS_DIVISOR = 2
SKIP_HONESTY_POINTS = 2


def _now() -> datetime:
    """Текущее время по UTC (с таймзоной) — именно его ставит сервер при отметке."""
    return datetime.now(timezone.utc)


def _habit_entries(db: Session, habit_id: int) -> list[HabitHistory]:
    return db.exec(select(HabitHistory).where(HabitHistory.h_id == habit_id)).all()


def _habit_dates(db: Session, habit_id: int, user: User, kinds: tuple = None) -> set:
    """Даты (без времени, по поясу пользователя) отметок привычки, опционально только нужных видов (kind)."""
    entries = _habit_entries(db, habit_id)
    if kinds:
        entries = [e for e in entries if e.kind in kinds]
    return {local_date(user, e.time) for e in entries}


def _bonus_freezes_for(db: Session, uid: int) -> dict:
    rows = db.exec(select(BonusFreeze).where(BonusFreeze.uid == uid)).all()
    return {r.week_key: r.amount for r in rows}


def habit_logged_today(db: Session, habit_id: int, user: User) -> bool:
    """Есть ли сегодня (по поясу пользователя) хоть какая-то отметка (done/minimal/skip)."""
    return today_for(user) in _habit_dates(db, habit_id, user)


def habit_due_today(habit: Habit, user: User) -> bool:
    """Запланирована ли привычка на сегодня по поясу пользователя (для daily — всегда да)."""
    if habit.frequency != "weekly" or not habit.weekdays:
        return True
    today_weekday = str(today_for(user).weekday())
    return today_weekday in habit.weekdays.split(",")


def habits_at_risk(db: Session, user: User) -> list[Habit]:
    """
    Привычки, которые вчера пропустили полностью (без единой отметки) —
    для мягкого экрана возврата ("не пропускай дважды").
    """
    yesterday = today_for(user) - timedelta(days=1)
    habits = db.exec(select(Habit).where(Habit.uid == user.id)).all()
    at_risk = []
    for habit in habits:
        if not habit_due_today(habit, user):
            continue
        if habit_logged_today(db, habit.id, user):
            continue
        dates = _habit_dates(db, habit.id, user)
        if yesterday not in dates:
            at_risk.append(habit)
    return at_risk


def _habits_context(db: Session, user: User, error: str = None) -> dict:
    """Собирает данные для шаблона habits.html: привычки + streak + статус за сегодня."""
    habits = db.exec(select(Habit).where(Habit.uid == user.id)).all()
    bonus_freezes = _bonus_freezes_for(db, user.id)
    habits_with_info = []
    for habit in habits:
        done_dates = _habit_dates(db, habit.id, user, kinds=("done", "minimal"))
        skip_dates = _habit_dates(db, habit.id, user, kinds=("skip",))
        streak_info = calculate_streak_with_freeze(done_dates, skip_dates, bonus_freezes)
        habits_with_info.append(
            {
                "habit": habit,
                "done_today": today_for(user) in done_dates,
                "streak": streak_info["streak"],
                "freezes_left": streak_info["freezes_left"],
                "due_today": habit_due_today(habit, user),
            }
        )
    return {"user": user, "habits": habits_with_info, "error": error, "catalog": CATALOG, "spheres": SPHERES}


@router.get("/habits")
def habits_list(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    """Список привычек пользователя с отметкой «сделано сегодня», streak и заморозками."""
    return render(
        request, "habits.html",
        _habits_context(db, user),
        db=db, user=user,
    )


@router.post("/habits")
def habit_create(
    request: Request,
    source: str = Form("custom"),  # "catalog" (готовая привычка) или "custom" (своя)
    catalog_code: str = Form(None),
    name: str = Form(None),
    description: str = Form(None),
    sphere: str = Form(None),
    difficulty: str = Form("medium"),
    habit_type: str = Form("useful"),
    frequency: str = Form("daily"),
    weekdays: Optional[List[str]] = Form(None),
    requires_proof: Optional[str] = Form(None),
    minimal_description: str = Form(None),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """
    Создаёт новую привычку — из каталога типовых (сфера+сложность уже заданы)
    или свою (сферу выбирает пользователь, сложность считает сервер по
    ключевым словам/Claude — пользователь не может поставить её выше расчётной).
    """
    if source == "catalog" and catalog_code:
        catalog_item = find_by_code(catalog_code)
        if not catalog_item:
            return render(
                request, "habits.html",
                _habits_context(db, user, "Привычка из каталога не найдена"),
                db=db, user=user, status_code=400,
            )
        final_name = catalog_item["name"]
        final_sphere = catalog_item["sphere"]
        final_difficulty = catalog_item["difficulty"]
        final_catalog_code = catalog_item["code"]
    else:
        if not name or not sphere or sphere not in SPHERES:
            return render(
                request, "habits.html",
                _habits_context(db, user, "Укажи название и сферу привычки"),
                db=db, user=user, status_code=400,
            )
        calculated = calculate_difficulty(name, description)
        final_difficulty = clamp_difficulty(difficulty, calculated)
        final_name = name
        final_sphere = sphere
        final_catalog_code = None

    habit = Habit(
        uid=user.id,
        name=final_name,
        description=description,
        point=points_for_habit_difficulty(final_difficulty),
        story_point=1.0,
        habit_type=habit_type,
        frequency=frequency,
        weekdays=",".join(weekdays) if frequency == "weekly" and weekdays else None,
        requires_proof=bool(requires_proof),
        minimal_description=minimal_description,
        sphere=final_sphere,
        catalog_code=final_catalog_code,
    )
    db.add(habit)

    user.habits += 1
    db.add(user)

    db.commit()

    newly_earned = check_and_award_achievements(db, user)
    for achievement in newly_earned:
        push_flash(request, f"{achievement.icon} Новое достижение: «{achievement.name}»!", "achievement")

    return render(
        request, "habits.html",
        _habits_context(db, user),
        db=db, user=user,
    )


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

    done_dates = _habit_dates(db, habit_id, user, kinds=("done", "minimal"))
    skip_dates = _habit_dates(db, habit_id, user, kinds=("skip",))
    all_dates = done_dates | skip_dates
    today = today_for(user)

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
    missed_days = [d["date"] for d in days if d["kind"] is None and d["date"] < today]

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
            "missed_days": missed_days,
        },
        db=db,
        user=user,
    )


@router.post("/habits/{habit_id}/use-freeze")
def use_freeze_route(
    habit_id: int,
    request: Request,
    day: str = Form(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """Тратит запасённую заморозку на конкретный пропущенный день (см. app/services/shop.py)."""
    habit = db.get(Habit, habit_id)
    if habit and habit.uid == user.id:
        try:
            target_day = datetime.strptime(day, "%Y-%m-%d").date()
        except ValueError:
            target_day = None
        if target_day:
            ok, message = use_freeze(db, user, habit, target_day)
            push_flash(request, message, "success" if ok else "error")

    return habit_detail(habit_id, request, user, db)


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

    if habit_logged_today(db, habit_id, user):
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

    # "Пробуждение" проверяем ДО записи отметки — иначе отметка сама же
    # обновит "последнюю активность", и личность никогда не окажется "спит"
    was_waking = kind != "skip" and is_waking(db, user.id, habit.sphere)

    # Время ставит сервер, игнорируя всё, что мог бы прислать клиент
    entry = HabitHistory(h_id=habit_id, time=_now(), kind=kind, proof_path=proof_path)
    db.add(entry)
    db.commit()

    if kind == "skip":
        level, leveled_up = award_points(db, user, SKIP_HONESTY_POINTS)
        push_flash(request, f"Честно признано 🙏 +{SKIP_HONESTY_POINTS} очка за честность")
        push_flash(request, skip_line(habit.sphere), "persona")
    else:
        base_points = habit.point if kind == "done" else max(1, habit.point // MINIMAL_POINTS_DIVISOR)
        if was_waking:
            base_points = round(base_points * (1 + WAKING_XP_BONUS))

        level, leveled_up = award_points(db, user, base_points)
        awarded_sphere_xp = log_sphere_xp(db, user.id, habit.sphere, base_points)
        sphere_name = SPHERES.get(habit.sphere, habit.sphere)
        if awarded_sphere_xp > 0:
            push_flash(request, f"+{base_points} очков 🎉 (+{awarded_sphere_xp} XP «{sphere_name}»)")
        else:
            push_flash(request, f"+{base_points} очков 🎉 (дневной лимит XP «{sphere_name}» уже набран)")
        if was_waking:
            push_flash(request, f"✨ Пробуждение! «{sphere_name}» вернулась в строй — очки +{int(WAKING_XP_BONUS * 100)}%")

        difficulty = difficulty_from_points(habit.point)
        coin_amount = HABIT_COINS.get(difficulty, HABIT_COINS["medium"]) + (PROOF_PHOTO_BONUS if proof_path else 0)
        awarded_coins = award_coins(db, user, coin_amount)
        if awarded_coins:
            push_flash(request, f"+{awarded_coins} 🪙", "coins")

        new_streak = calculate_streak_with_freeze(
            _habit_dates(db, habit_id, user, kinds=("done", "minimal")),
            _habit_dates(db, habit_id, user, kinds=("skip",)),
            _bonus_freezes_for(db, user.id),
        )["streak"]
        if is_streak_milestone(new_streak):
            push_flash(request, streak_line(habit.sphere, new_streak), "persona")

    if leveled_up:
        push_flash(request, level_up_message(level_for_xp(level.point)), "level-up")

    refresh_trust_score(db, user)
    evaluate_bets_for_habit(db, habit_id)
    evaluate_partnerships_for_habit(db, habit_id)

    chest = maybe_award_chest(db, user, habit)
    if chest:
        push_flash(request, f"🎁 Сундук за неделю без пропусков: {chest.reward_value}!", f"chest-{chest.rarity}")

    if kind == "done":
        new_difficulty = maybe_recalibrate(db, habit)
        if new_difficulty:
            push_flash(
                request,
                f"«{habit.name}» выполнялась 30 дней подряд без пропусков — "
                f"сложность снижена до «{new_difficulty}», она явно стала легче 💪",
                "recalibration",
            )

    newly_earned = check_and_award_achievements(db, user)
    for achievement in newly_earned:
        push_flash(request, f"{achievement.icon} Новое достижение: «{achievement.name}»!", "achievement")

    return render(request, "habits.html", _habits_context(db, user), db=db, user=user)
