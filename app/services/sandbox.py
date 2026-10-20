"""
Песочница /admin/sandbox (v6d): меняет прогресс СВОЕГО аккаунта напрямую,
без прохождения обычных проверок — для осмотра всех визуальных состояний
игры (стадии личностей, питомца, героя) без недель реальной игры.

Правила (см. DECISIONS.md, п.18-19):
- первая правка создаёт снимок реального прогресса (SandboxSnapshot) —
  повторные правки его не трогают, "сбросить" возвращает именно эти числа;
- любая правка выставляет User.is_test = True навсегда (сам флаг сброс не
  снимает — только числа возвращаются к снимку);
- уровень сферы хранится ОДНОЙ записью PointsLog (её time одновременно
  задаёт состояние личности — активна/дремлет/спит), чтобы два контрола
  не могли "спорить" друг с другом;
- серия дней — через скрытую привычку `_sandbox_streak` (не показывается
  в обычном списке — фильтруется по имени), не трогает реальные привычки;
- "выдать всё" — чит на осмотр контента: создаёт записи напрямую, монеты
  за это не начисляются и это НЕ входит в снимок (не отменяется сбросом).
"""

import json
from datetime import date, datetime, timedelta, timezone

from sqlmodel import Session, select

from app.models import (
    Achievement,
    Habit,
    HabitHistory,
    InventoryItem,
    Level,
    Pet,
    PointsLog,
    SandboxSnapshot,
    ShopItem,
    User,
    UserAchievement,
    WeeklyCouncilMessage,
)
from app.services.achievements import CATALOG as ACHIEVEMENTS_CATALOG
from app.services.bosses import active_group_for_user, create_group, deal_damage
from app.services.chests import grant_chest
from app.services.levels import xp_threshold_for_level
from app.services.pets import PET_SPECIES, get_or_create_pet
from app.services.persona_voices import council_line
from app.services.personas import PERSONAS
from app.services.spheres import MAX_LEVEL as SPHERE_MAX_LEVEL
from app.services.spheres import SPHERES, XP_PER_LEVEL, sphere_level, sphere_xp
from app.services.streak import _week_key

SANDBOX_STREAK_HABIT_NAME = "_sandbox_streak"

SPHERE_STATE_DAYS_AGO = {"активна": 0, "дремлет": 10, "спит": 25}

PRESETS = ["newbie", "midway", "legend", "all_sleeping", "harmony"]
PRESET_LABELS = {
    "newbie": "Новичок",
    "midway": "Середина пути (ур. 20)",
    "legend": "Легенда (ур. 50)",
    "all_sleeping": "Всё спит",
    "harmony": "Гармония",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_level(db: Session, user: User) -> Level:
    level = db.exec(select(Level).where(Level.uid == user.id)).first()
    if not level:
        level = Level(uid=user.id, point=0, name="Новичок")
        db.add(level)
        db.commit()
        db.refresh(level)
    return level


def _get_or_create_streak_habit(db: Session, user: User) -> Habit:
    habit = db.exec(
        select(Habit).where(Habit.uid == user.id, Habit.name == SANDBOX_STREAK_HABIT_NAME)
    ).first()
    if habit:
        return habit
    habit = Habit(uid=user.id, name=SANDBOX_STREAK_HABIT_NAME, status="active", habit_type="useful")
    db.add(habit)
    db.commit()
    db.refresh(habit)
    return habit


def mark_test_account(db: Session, user: User) -> None:
    """Выставляет is_test=True навсегда — любая правка в песочнице помечает аккаунт (п.19)."""
    if not user.is_test:
        user.is_test = True
        db.add(user)
        db.commit()


def ensure_snapshot(db: Session, user: User) -> None:
    """Если снимка ещё нет — сохраняет текущий реальный прогресс (только то, чем управляют контролы)."""
    existing = db.exec(select(SandboxSnapshot).where(SandboxSnapshot.uid == user.id)).first()
    if existing:
        return

    level = _get_level(db, user)
    pet = get_or_create_pet(db, user.id)
    data = {
        "level_point": level.point,
        "sphere_xp": {code: sphere_xp(db, user.id, code) for code in SPHERES},
        "coins": user.coins,
        "trust_score": user.trust_score,
        "pet_species": pet.species,
        "pet_stage": pet.best_stage_reached,
    }
    db.add(SandboxSnapshot(uid=user.id, data=json.dumps(data)))
    db.commit()


def set_hero_level(db: Session, user: User, level_number: int) -> None:
    mark_test_account(db, user)
    ensure_snapshot(db, user)
    level = _get_level(db, user)
    level.point = xp_threshold_for_level(level_number)
    db.add(level)
    db.commit()


def set_sphere(db: Session, user: User, sphere_code: str, level_number: int, state: str) -> None:
    """Одна запись PointsLog задаёт и уровень сферы (points), и состояние личности (time)."""
    if sphere_code not in SPHERES:
        return
    mark_test_account(db, user)
    ensure_snapshot(db, user)

    level_number = max(1, min(level_number, SPHERE_MAX_LEVEL))
    xp = (level_number - 1) * XP_PER_LEVEL
    days_ago = SPHERE_STATE_DAYS_AGO.get(state, 0)

    old_logs = db.exec(select(PointsLog).where(PointsLog.uid == user.id, PointsLog.sphere == sphere_code)).all()
    for log in old_logs:
        db.delete(log)
    db.add(PointsLog(uid=user.id, points=xp, sphere=sphere_code, time=_now() - timedelta(days=days_ago)))
    db.commit()


def set_streak(db: Session, user: User, days: int) -> None:
    mark_test_account(db, user)
    ensure_snapshot(db, user)

    habit = _get_or_create_streak_habit(db, user)
    old_entries = db.exec(select(HabitHistory).where(HabitHistory.h_id == habit.id)).all()
    for entry in old_entries:
        db.delete(entry)
    db.commit()

    today = date.today()
    for i in range(max(0, days)):
        day = today - timedelta(days=i)
        db.add(HabitHistory(h_id=habit.id, time=datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc), kind="done"))
    db.commit()


def set_pet(db: Session, user: User, species: str | None, stage: int) -> None:
    mark_test_account(db, user)
    ensure_snapshot(db, user)

    pet = get_or_create_pet(db, user.id)
    pet.species = species if species in PET_SPECIES else None
    pet.best_stage_reached = max(1, min(stage, 5))
    db.add(pet)
    db.commit()


def set_coins(db: Session, user: User, coins: int) -> None:
    mark_test_account(db, user)
    ensure_snapshot(db, user)
    user.coins = max(0, coins)
    db.add(user)
    db.commit()


def set_trust_score(db: Session, user: User, trust_score: int) -> None:
    mark_test_account(db, user)
    ensure_snapshot(db, user)
    user.trust_score = max(0, min(100, trust_score))
    db.add(user)
    db.commit()


def grant_all_items(db: Session, user: User) -> int:
    """Выдаёт все предметы магазина (кроме заморозки — она расходуемая, не инвентарь). Без монет (п.18)."""
    mark_test_account(db, user)
    owned = {r.item_code for r in db.exec(select(InventoryItem).where(InventoryItem.uid == user.id)).all()}
    items = db.exec(select(ShopItem).where(ShopItem.slot != "freeze")).all()
    granted = 0
    for item in items:
        if item.code in owned:
            continue
        db.add(InventoryItem(uid=user.id, item_code=item.code))
        granted += 1
    db.commit()
    return granted


def grant_all_achievements(db: Session, user: User) -> int:
    """Выдаёт все достижения каталога. Без монет (п.18)."""
    mark_test_account(db, user)
    earned_ids = {r.achievement_id for r in db.exec(select(UserAchievement).where(UserAchievement.uid == user.id)).all()}
    achievements = db.exec(select(Achievement)).all()
    granted = 0
    for achievement in achievements:
        if achievement.id in earned_ids:
            continue
        db.add(UserAchievement(uid=user.id, achievement_id=achievement.id))
        granted += 1
    db.commit()
    return granted


def open_chest_of_rarity(db: Session, user: User, rarity: str):
    mark_test_account(db, user)
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    return grant_chest(db, user, week_start, habit_id=None, forced_rarity=rarity)


def run_council_now(db: Session, user: User) -> list[dict]:
    """Та же запись, что и обычная генерация совета недели, но без гейта 'воскресенье и ур.10+'."""
    mark_test_account(db, user)
    week = _week_key(date.today())
    week_start = date.today() - timedelta(days=6)

    existing = db.exec(
        select(WeeklyCouncilMessage).where(WeeklyCouncilMessage.uid == user.id, WeeklyCouncilMessage.week_key == week)
    ).all()
    for row in existing:
        db.delete(row)
    db.commit()

    messages = []
    for code in PERSONAS:
        logs = db.exec(select(PointsLog).where(PointsLog.uid == user.id, PointsLog.sphere == code)).all()
        week_xp = sum(log.points for log in logs if log.time.date() >= week_start)
        text = council_line(code, week_xp)
        db.add(WeeklyCouncilMessage(uid=user.id, week_key=week, persona_code=code, text=text))
        messages.append({"persona_name": PERSONAS[code], "text": text})
    db.commit()
    return messages


def boss_hit(db: Session, user: User, damage: int):
    mark_test_account(db, user)
    group = active_group_for_user(db, user.id)
    if not group:
        group, _ = create_group(db, user, hero_level=99)
    if not group:
        return None
    return deal_damage(db, user, max(1, damage))


def boss_finish(db: Session, user: User):
    mark_test_account(db, user)
    group = active_group_for_user(db, user.id)
    if not group:
        group, _ = create_group(db, user, hero_level=99)
    if not group or group.hp_remaining <= 0:
        return group
    return deal_damage(db, user, group.hp_remaining)


def reset_to_snapshot(db: Session, user: User) -> bool:
    """Возвращает числа к снимку реального прогресса. is_test остаётся True (п.19)."""
    snapshot = db.exec(select(SandboxSnapshot).where(SandboxSnapshot.uid == user.id)).first()
    if not snapshot:
        return False

    data = json.loads(snapshot.data)

    level = _get_level(db, user)
    level.point = data["level_point"]
    db.add(level)

    for code, xp in data["sphere_xp"].items():
        old_logs = db.exec(select(PointsLog).where(PointsLog.uid == user.id, PointsLog.sphere == code)).all()
        for log in old_logs:
            db.delete(log)
        if xp:
            db.add(PointsLog(uid=user.id, points=xp, sphere=code, time=_now()))

    user.coins = data["coins"]
    user.trust_score = data["trust_score"]
    db.add(user)

    pet = get_or_create_pet(db, user.id)
    pet.species = data["pet_species"]
    pet.best_stage_reached = data["pet_stage"]
    db.add(pet)

    db.commit()
    return True


def apply_preset(db: Session, user: User, preset: str) -> str:
    if preset == "newbie":
        set_hero_level(db, user, 1)
        for code in SPHERES:
            set_sphere(db, user, code, 1, "активна")
        set_streak(db, user, 0)
        set_pet(db, user, None, 1)
        set_coins(db, user, 0)
        set_trust_score(db, user, 100)
    elif preset == "midway":
        set_hero_level(db, user, 20)
        for code in SPHERES:
            set_sphere(db, user, code, 10, "активна")
        set_streak(db, user, 15)
        set_pet(db, user, "fox", 2)
        set_coins(db, user, 200)
        set_trust_score(db, user, 80)
    elif preset == "legend":
        set_hero_level(db, user, 50)
        for code in SPHERES:
            set_sphere(db, user, code, 20, "активна")
        set_streak(db, user, 365)
        set_pet(db, user, "drake", 5)
        set_coins(db, user, 1000)
        set_trust_score(db, user, 100)
    elif preset == "all_sleeping":
        for code in SPHERES:
            current_level = sphere_level(sphere_xp(db, user.id, code)) or 1
            set_sphere(db, user, code, current_level, "спит")
        set_streak(db, user, 0)
    elif preset == "harmony":
        for code in SPHERES:
            current_level = sphere_level(sphere_xp(db, user.id, code)) or 1
            set_sphere(db, user, code, current_level, "активна")
    else:
        return "Неизвестный пресет"

    return f"Применён пресет «{PRESET_LABELS.get(preset, preset)}»"
