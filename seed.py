"""
Скрипт с демо-данными — чтобы сразу увидеть приложение заполненным
(30 дней истории, достижения, шаги целей, рейтинг друзей, чат с коучем).
Запуск: python seed.py

Безопасно перезапускать — данные не дублируются (проверяется по наличию
привычек/целей у demo).
"""

from datetime import date, datetime, timedelta, timezone

from sqlmodel import Session, select

from app.auth import hash_password
from app.database import create_db_and_tables, engine
from app.models import (
    CoachMessage,
    Education,
    Friend,
    Goal,
    GoalHistory,
    GoalStep,
    Habit,
    HabitHistory,
    Level,
    PointsLog,
    Registration,
    Training,
    User,
)
from app.services.achievements import check_and_award_achievements, ensure_achievements_seeded
from app.services.daily_tasks import get_or_create_today_tasks
from app.services.points import level_name_for_points


def _now() -> datetime:
    return datetime.now(timezone.utc)


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


def _award_points_at(db: Session, user: User, points: int, when: datetime) -> None:
    """Начисляет очки с произвольной (возможно, прошедшей) датой — для реалистичного графика."""
    level = db.exec(select(Level).where(Level.uid == user.id)).first()
    level.point += points
    level.name = level_name_for_points(level.point)
    db.add(level)
    db.add(PointsLog(uid=user.id, points=points, time=when))
    db.commit()


def _seed_habits(db: Session, demo: User) -> None:
    if demo.habits > 0:
        return  # уже заполнено

    water = Habit(
        uid=demo.id, name="Пить воду", description="8 стаканов в день",
        point=10, story_point=1.0, habit_type="useful", frequency="daily",
    )
    reading = Habit(
        uid=demo.id, name="Читать книгу", description="30 минут перед сном",
        point=15, story_point=1.0, habit_type="useful", frequency="daily",
    )
    no_smoking = Habit(
        uid=demo.id, name="Не курить", description="день без срыва",
        point=20, story_point=1.0, habit_type="harmful", frequency="weekly", weekdays="0,2,4",
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

    # "Пить воду" — чистая серия 30 дней подряд (для достижений streak_7 / streak_30)
    for days_ago in range(30):
        when = today - timedelta(days=days_ago)
        db.add(HabitHistory(h_id=water.id, time=when))
        db.commit()
        _award_points_at(db, demo, water.point, when)

    # "Читать книгу" — реже, со случайными пропусками (для графика с разбросом)
    for days_ago in [1, 2, 4, 5, 6, 9, 10, 13, 14, 15, 18, 21, 22, 25, 27]:
        when = today - timedelta(days=days_ago)
        db.add(HabitHistory(h_id=reading.id, time=when))
        db.commit()
        _award_points_at(db, demo, reading.point, when)

    # "Не курить" — несколько отметок
    for days_ago in [0, 2, 4, 7, 9]:
        when = today - timedelta(days=days_ago)
        db.add(HabitHistory(h_id=no_smoking.id, time=when))
        db.commit()
        _award_points_at(db, demo, no_smoking.point, when)


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


def main() -> None:
    create_db_and_tables()
    with Session(engine) as db:
        ensure_achievements_seeded(db)

        demo = _get_or_create_user(
            db, name="Демо Пользователь", age=25, gender="male",
            mail="demo@example.com", login="demo", password="demo1234",
        )
        friend = _get_or_create_user(
            db, name="Друг Демо", age=23, gender="female",
            mail="friend@example.com", login="friend_demo", password="demo1234",
        )

        _seed_habits(db, demo)
        _seed_goals(db, demo)
        _seed_friendship_and_leaderboard(db, demo, friend)
        _seed_coach_history(db, demo)

        check_and_award_achievements(db, demo)
        check_and_award_achievements(db, friend)

        get_or_create_today_tasks(db, demo)

    print("Демо-данные готовы!")
    print("Логин: demo          Пароль: demo1234")
    print("Логин: friend_demo   Пароль: demo1234")


if __name__ == "__main__":
    main()
