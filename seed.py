"""
Скрипт с демо-данными — чтобы сразу увидеть приложение заполненным.
Запуск: python seed.py

Создаёт:
- пользователя demo / demo1234 с привычками (одна с серией в 3 дня),
  мечтой, завершённой и текущей целью, программами обучения;
- пользователя friend_demo / demo1234, уже добавленного в друзья к demo.
Скрипт безопасно перезапускать — данные не дублируются.
"""

from datetime import date, datetime, timedelta, timezone

from sqlmodel import Session, select

from app.auth import hash_password
from app.database import create_db_and_tables, engine
from app.models import (
    Education,
    Friend,
    Goal,
    GoalHistory,
    Habit,
    HabitHistory,
    Level,
    Registration,
    Training,
    User,
)
from app.services.points import award_points


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


def _seed_habits(db: Session, demo: User) -> None:
    if demo.habits > 0:
        return  # уже заполнено

    water = Habit(uid=demo.id, name="Пить воду", description="8 стаканов в день", point=10, story_point=1.0)
    reading = Habit(uid=demo.id, name="Читать книгу", description="30 минут перед сном", point=15, story_point=1.2)
    db.add(water)
    db.add(reading)
    demo.habits += 2
    db.add(demo)
    db.commit()
    db.refresh(water)

    # Серия из 3 дней подряд для "Пить воду"
    for days_ago in range(3):
        db.add(HabitHistory(h_id=water.id, time=_now() - timedelta(days=days_ago)))
    db.commit()
    award_points(db, demo, int(water.point * water.story_point) * 3)


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
        story_point=1.5,
        parent_id=dream.id,
    )
    db.add(done_goal)
    db.add(active_goal)
    demo.goals += 2
    db.add(demo)
    db.commit()
    db.refresh(done_goal)
    db.refresh(active_goal)

    db.add(GoalHistory(h_id=done_goal.id, time=_now() - timedelta(days=5)))
    db.add(GoalHistory(h_id=done_goal.id, time=_now() - timedelta(days=1)))
    db.add(GoalHistory(h_id=active_goal.id, time=_now()))
    db.commit()

    award_points(db, demo, int(done_goal.point * done_goal.story_point))

    db.add(Training(uid=demo.id, g_id=active_goal.id, name="Алгоритмы", program="Решать 1 задачу в день"))
    db.add(Education(uid=demo.id, g_id=active_goal.id, name="Курс FastAPI", program="20 уроков"))
    db.commit()


def _seed_friendship(db: Session, demo: User, friend: User) -> None:
    existing = db.exec(
        select(Friend).where(
            ((Friend.uid == demo.id) & (Friend.friend_id == friend.id))
            | ((Friend.uid == friend.id) & (Friend.friend_id == demo.id))
        )
    ).first()
    if not existing:
        db.add(Friend(uid=friend.id, friend_id=demo.id, status="accepted"))
        db.commit()


def main() -> None:
    create_db_and_tables()
    with Session(engine) as db:
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
        _seed_friendship(db, demo, friend)

    print("Демо-данные готовы!")
    print("Логин: demo          Пароль: demo1234")
    print("Логин: friend_demo   Пароль: demo1234")


if __name__ == "__main__":
    main()
