"""
Скрипт с демо-данными — чтобы сразу увидеть приложение заполненным
(30 дней истории, достижения, шаги целей, рейтинг друзей, чат с коучем).
Запуск: python seed.py

Безопасно перезапускать — данные не дублируются (проверяется по наличию
привычек/целей у demo).
"""

import base64
import os
from datetime import date, datetime, timedelta, timezone

from sqlmodel import Session, select

from app.auth import hash_password
from app.database import engine
from app.migrations_runner import run_migrations
from app.models import (
    Bet,
    Chest,
    CoachMessage,
    Education,
    Friend,
    Goal,
    GoalHistory,
    GoalStep,
    Habit,
    HabitConfirmation,
    HabitHistory,
    Level,
    Partnership,
    PointsLog,
    Registration,
    Training,
    User,
)
from app.services.achievements import check_and_award_achievements, ensure_achievements_seeded
from app.services.daily_tasks import get_or_create_today_tasks
from app.services.levels import level_for_xp
from app.services.points import level_name_for_points
from app.services.shop import buy_item, ensure_shop_seeded, equip_item
from app.services.trust import refresh_trust_score


def _now() -> datetime:
    return datetime.now(timezone.utc)


# Крошечный валидный JPEG (1x1 пиксель) — для демо-фото-доказательств, чтобы
# на странице друзей картинка реально открывалась, а не была "битой".
_PLACEHOLDER_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAMDAwMDAwQEBAQFBQUFBQcGBgYGBwkICQkJCQkMDAwM"
    "DAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAz/wAALCAABAAEBAREA/8QAFAAB"
    "AAAAAAAAAAAAAAAAAAAACP/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AVAr/2Q=="
)


def _write_placeholder_photo(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(_PLACEHOLDER_JPEG)


def _get_or_create_user(db: Session, *, name, age, gender, mail, login, password) -> User:
    """Создаёт пользователя (регистрация + профиль + уровень), либо возвращает существующего."""
    existing = db.exec(select(Registration).where(Registration.login == login)).first()
    if existing:
        return db.exec(select(User).where(User.login == login)).first()

    db.add(
        Registration(
            name=name, age=age, gender=gender, mail=mail, login=login, password=hash_password(password)
        )
    )
    db.commit()

    user = User(mail=mail, login=login, habits=0, goals=0)
    db.add(user)
    db.commit()
    db.refresh(user)

    db.add(Level(uid=user.id, point=0, name="Новичок"))
    db.commit()
    return user


def _award_points_at(db: Session, user: User, points: int, when: datetime, sphere: str = None) -> None:
    """
    Начисляет очки с произвольной (возможно, прошедшей) датой — для реалистичного
    графика. Если указана sphere — тот же XP идёт и в личность этой сферы
    (как в реальной отметке привычки, см. app/routers/habits.py::habit_check).
    """
    level = db.exec(select(Level).where(Level.uid == user.id)).first()
    level.point += points
    level.name = level_name_for_points(level.point)
    db.add(level)
    db.add(PointsLog(uid=user.id, points=points, time=when, sphere=sphere))
    db.commit()


def _seed_habits(db: Session, demo: User) -> tuple:
    """Создаёт привычки с историей. Если уже заполнено — просто возвращает их."""
    if demo.habits > 0:
        existing = db.exec(select(Habit).where(Habit.uid == demo.id)).all()
        by_name = {h.name: h for h in existing}
        water_entries = db.exec(
            select(HabitHistory).where(HabitHistory.h_id == by_name["Пить воду"].id)
        ).all()
        return by_name["Пить воду"], by_name["Читать книгу"], by_name["Не курить"], water_entries

    water = Habit(
        uid=demo.id, name="Пить воду", description="8 стаканов в день",
        point=10, story_point=1.0, habit_type="useful", frequency="daily",
        requires_proof=True, minimal_description="выпить хотя бы 1 стакан",
        sphere="health",
    )
    reading = Habit(
        uid=demo.id, name="Читать книгу", description="30 минут перед сном",
        point=15, story_point=1.0, habit_type="useful", frequency="daily",
        minimal_description="прочитать хотя бы 5 страниц",
        sphere="intellect",
    )
    no_smoking = Habit(
        uid=demo.id, name="Не курить", description="день без срыва",
        point=20, story_point=1.0, habit_type="harmful", frequency="weekly", weekdays="0,2,4",
        sphere="discipline",
    )
    db.add(water)
    db.add(reading)
    db.add(no_smoking)
    demo.habits += 3
    db.add(demo)
    db.commit()
    db.refresh(water)
    db.refresh(reading)
    db.refresh(no_smoking)

    today = _now()

    # "Пить воду" — серия 30 дней почти без дыр: один честный пропуск (заморозка
    # спасает серию) и свежие отметки с фото-доказательством (растит trust score)
    water_entries = []
    for days_ago in range(30):
        when = today - timedelta(days=days_ago)
        if days_ago == 3:
            entry = HabitHistory(h_id=water.id, time=when, kind="skip")
            db.add(entry)
            db.commit()
            _award_points_at(db, demo, 2, when, sphere="health")
        else:
            proof = f"uploads/seed_demo_water_{days_ago}.jpg"
            _write_placeholder_photo(proof)
            entry = HabitHistory(h_id=water.id, time=when, kind="done", proof_path=proof)
            db.add(entry)
            db.commit()
            _award_points_at(db, demo, water.point, when, sphere="health")
        db.refresh(entry)
        water_entries.append(entry)

    # "Читать книгу" — реже, с минимальными версиями и пропусками (для графика с разбросом)
    minimal_days = {5, 14, 22}
    for days_ago in [1, 2, 4, 5, 6, 9, 10, 13, 14, 15, 18, 21, 22, 25, 27]:
        when = today - timedelta(days=days_ago)
        kind = "minimal" if days_ago in minimal_days else "done"
        points = max(1, reading.point // 2) if kind == "minimal" else reading.point
        proof = f"uploads/seed_demo_reading_{days_ago}.jpg"
        _write_placeholder_photo(proof)
        db.add(HabitHistory(h_id=reading.id, time=when, kind=kind, proof_path=proof))
        db.commit()
        _award_points_at(db, demo, points, when, sphere="intellect")

    # "Не курить" — несколько отметок
    for days_ago in [0, 2, 4, 7, 9]:
        when = today - timedelta(days=days_ago)
        proof = f"uploads/seed_demo_smoking_{days_ago}.jpg"
        _write_placeholder_photo(proof)
        db.add(HabitHistory(h_id=no_smoking.id, time=when, proof_path=proof))
        db.commit()
        _award_points_at(db, demo, no_smoking.point, when, sphere="discipline")

    return water, reading, no_smoking, water_entries


def _seed_personas(db: Session, demo: User) -> None:
    """
    Прокачивает оставшиеся 2 личности демо так, чтобы профиль героя выглядел
    живым: Воин (Сила) — активен в последние дни, Бард (Харизма) — был
    активен месяц назад и с тех пор "спит" (21+ дней тишины), для демонстрации
    состояний личностей на /hero.
    """
    existing = db.exec(select(PointsLog).where(PointsLog.uid == demo.id, PointsLog.sphere == "strength")).first()
    if existing:
        return  # уже засеяно

    today = _now()

    # Воин (Сила) — активен: 8 отметок за последние 2 недели
    for days_ago in [0, 1, 3, 4, 6, 8, 10, 13]:
        _award_points_at(db, demo, 10, today - timedelta(days=days_ago), sphere="strength")

    # Бард (Харизма) — активничал месяц назад, потом затих -> состояние "спит"
    for days_ago in [26, 28, 30]:
        _award_points_at(db, demo, 10, today - timedelta(days=days_ago), sphere="charisma")


def _seed_goals(db: Session, demo: User) -> None:
    if demo.goals > 0:
        return  # уже заполнено

    dream = Goal(uid=demo.id, name="Стать разработчиком", description="Моя главная мечта", parent_id=None)
    db.add(dream)
    demo.goals += 1
    db.add(demo)
    db.commit()
    db.refresh(dream)

    done_goal = Goal(
        uid=demo.id,
        name="Выучить основы Python",
        description="Переменные, функции, классы",
        status="completed",
        point=100,
        story_point=1.0,
        parent_id=dream.id,
    )
    active_goal = Goal(
        uid=demo.id,
        name="Сделать дипломный проект",
        description="MVP на FastAPI",
        deadline=date.today() + timedelta(days=14),
        point=200,
        story_point=1.0,
        parent_id=dream.id,
    )
    db.add(done_goal)
    db.add(active_goal)
    demo.goals += 2
    db.add(demo)
    db.commit()
    db.refresh(done_goal)
    db.refresh(active_goal)

    db.add(GoalHistory(h_id=done_goal.id, time=_now() - timedelta(days=20)))
    db.add(GoalHistory(h_id=done_goal.id, time=_now() - timedelta(days=15)))
    db.commit()
    _award_points_at(db, demo, done_goal.point, _now() - timedelta(days=15))

    # Шаги активной цели: половина выполнена (прогресс-бар = 50%)
    steps = [
        GoalStep(goal_id=active_goal.id, name="Выбрать тему проекта", done=True),
        GoalStep(goal_id=active_goal.id, name="Написать план", done=True),
        GoalStep(goal_id=active_goal.id, name="Реализовать MVP", done=False),
        GoalStep(goal_id=active_goal.id, name="Защитить проект", done=False),
    ]
    for step in steps:
        db.add(step)
    db.commit()

    db.add(Training(uid=demo.id, g_id=active_goal.id, name="Алгоритмы", program="Решать 1 задачу в день"))
    db.add(Education(uid=demo.id, g_id=active_goal.id, name="Курс FastAPI", program="20 уроков"))
    db.commit()


def _seed_friend_habit(db: Session, friend: User) -> Habit:
    """Даёт другу привычку с короткой свежей серией — нужна для демо напарника."""
    existing = db.exec(select(Habit).where(Habit.uid == friend.id)).first()
    if existing:
        return existing

    habit = Habit(uid=friend.id, name="Зарядка", point=10, story_point=1.0)
    db.add(habit)
    friend.habits += 1
    db.add(friend)
    db.commit()
    db.refresh(habit)

    today = _now()
    for days_ago in range(3):
        proof = f"uploads/seed_friend_{days_ago}.jpg"
        _write_placeholder_photo(proof)
        db.add(HabitHistory(h_id=habit.id, time=today - timedelta(days=days_ago), kind="done", proof_path=proof))
    db.commit()
    return habit


def _seed_friendship_and_leaderboard(db: Session, demo: User, friend: User) -> None:
    existing = db.exec(
        select(Friend).where(
            ((Friend.uid == demo.id) & (Friend.friend_id == friend.id))
            | ((Friend.uid == friend.id) & (Friend.friend_id == demo.id))
        )
    ).first()
    if existing:
        return

    db.add(Friend(uid=friend.id, friend_id=demo.id, status="accepted"))
    db.commit()

    # Немного очков у друга за последнюю неделю — для рейтинга
    _award_points_at(db, friend, 60, _now() - timedelta(days=2))
    _award_points_at(db, friend, 40, _now() - timedelta(days=4))


def _seed_bet(db: Session, demo: User, reading: Habit) -> None:
    """Активная ставка на 'Читать книгу' — демонстрирует механику ставок."""
    existing = db.exec(select(Bet).where(Bet.uid == demo.id)).first()
    if existing:
        return
    db.add(
        Bet(
            uid=demo.id, habit_id=reading.id, stake_points=30, target_days=5,
            start_date=date.today(), status="active",
        )
    )
    db.commit()


def _seed_partnership(db: Session, demo: User, friend: User, water: Habit, friend_habit: Habit) -> None:
    """Активное партнёрство 'напарник' между demo и friend_demo."""
    existing = db.exec(
        select(Partnership).where(
            (Partnership.uid_a == demo.id) | (Partnership.uid_b == demo.id)
        )
    ).first()
    if existing:
        return
    db.add(
        Partnership(
            uid_a=demo.id, habit_id_a=water.id, uid_b=friend.id, habit_id_b=friend_habit.id,
            status="active",
        )
    )
    db.commit()


def _seed_chest(db: Session, demo: User, water: Habit) -> None:
    """Исторический сундук — за одну из прошлых недель чистой серии 'Пить воду'."""
    existing = db.exec(select(Chest).where(Chest.uid == demo.id)).first()
    if existing:
        return
    week_start = (date.today() - timedelta(days=21)) - timedelta(days=(date.today() - timedelta(days=21)).weekday())
    db.add(
        Chest(
            uid=demo.id, habit_id=water.id, week_start=week_start,
            reward_type="points", reward_value="30", time=_now() - timedelta(days=20),
        )
    )
    db.commit()


def _seed_confirmation(db: Session, friend: User, water_entries: list) -> None:
    """Друг подтверждает самую свежую отметку 'Пить воду' — для ленты друзей."""
    recent_entry = next((e for e in water_entries if e.kind == "done" and e.proof_path), None)
    if not recent_entry:
        return
    existing = db.exec(
        select(HabitConfirmation).where(HabitConfirmation.history_id == recent_entry.id)
    ).first()
    if existing:
        return
    db.add(HabitConfirmation(history_id=recent_entry.id, confirmer_uid=friend.id, status="confirmed"))
    db.commit()


def _seed_coach_history(db: Session, demo: User) -> None:
    existing = db.exec(select(CoachMessage).where(CoachMessage.uid == demo.id)).first()
    if existing:
        return

    exchanges = [
        ("coach", "Привет! Я заметил твою серию в 30 дней по привычке «Пить воду» — это впечатляет 🔥", 10),
        ("user", "Спасибо! Как не потерять мотивацию дальше?", 9),
        ("coach", "Старайся не прерывать серию больше одного дня — оставь привычку максимально простой.", 9),
        ("user", "А как быстрее дойти до следующего уровня?", 3),
        ("coach", "Заверши активную цель и выполняй ежедневные задания — это быстрый бонус к очкам.", 3),
    ]
    for role, text, days_ago in exchanges:
        db.add(CoachMessage(uid=demo.id, role=role, text=text, time=_now() - timedelta(days=days_ago)))
    db.commit()


def _seed_shop_purchases(db: Session, demo: User) -> None:
    """
    Покупает демо пару недорогих предметов (монеты к этому моменту уже
    честно накопились от отметок/достижений) и надевает один из них —
    чтобы в инвентаре/магазине сразу было что показать.
    """
    db.refresh(demo)
    hero_level = level_for_xp(db.exec(select(Level).where(Level.uid == demo.id)).first().point)

    for code in ("bg_dawn", "frame_simple"):
        from app.services.shop import is_owned

        if not is_owned(db, demo.id, code):
            buy_item(db, demo, code, hero_level)
    equip_item(db, demo, "bg_dawn")
    equip_item(db, demo, "frame_simple")


def main() -> None:
    run_migrations()
    with Session(engine) as db:
        ensure_achievements_seeded(db)
        ensure_shop_seeded(db)

        demo = _get_or_create_user(
            db, name="Демо Пользователь", age=25, gender="male",
            mail="demo@example.com", login="demo", password="demo1234",
        )
        friend = _get_or_create_user(
            db, name="Друг Демо", age=23, gender="female",
            mail="friend@example.com", login="friend_demo", password="demo1234",
        )

        water, reading, no_smoking, water_entries = _seed_habits(db, demo)
        _seed_personas(db, demo)
        _seed_goals(db, demo)
        _seed_friendship_and_leaderboard(db, demo, friend)
        friend_habit = _seed_friend_habit(db, friend)
        _seed_bet(db, demo, reading)
        _seed_partnership(db, demo, friend, water, friend_habit)
        _seed_chest(db, demo, water)
        _seed_confirmation(db, friend, water_entries)
        _seed_coach_history(db, demo)

        check_and_award_achievements(db, demo)
        check_and_award_achievements(db, friend)

        refresh_trust_score(db, demo)
        refresh_trust_score(db, friend)

        get_or_create_today_tasks(db, demo)
        _seed_shop_purchases(db, demo)

    print("Демо-данные готовы!")
    print("Логин: demo          Пароль: demo1234")
    print("Логин: friend_demo   Пароль: demo1234")
    with Session(engine) as db:
        demo = db.exec(select(User).where(User.login == "demo")).first()
        print(f"У demo: {demo.coins} монет, предметы надеты (фон/рамка)")


if __name__ == "__main__":
    main()
