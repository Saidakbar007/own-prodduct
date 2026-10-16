"""
Ежедневные мини-задания (v2): 3 случайные задачи в день с бонусными очками.
Решение: пользователь сам отмечает выполнение кнопкой (без автоматической
проверки действия) — так проще и прозрачнее для MVP.
"""

import random
from datetime import date

from sqlmodel import Session, select

from app.models import DailyTask, User

TASK_POOL = [
    "Отметь одну привычку сегодня",
    "Добавь новую привычку",
    "Отметь прогресс по любой цели",
    "Загляни в статистику и посмотри на свой прогресс",
    "Проверь заявки в друзья",
    "Добавь шаг к одной из своих целей",
    "Спроси совет у AI-коуча",
]
TASK_POINTS = 20
TASKS_PER_DAY = 3


def get_or_create_today_tasks(db: Session, user: User) -> list[DailyTask]:
    """Возвращает сегодняшние задания пользователя, создавая их при первом обращении за день."""
    today = date.today()
    tasks = db.exec(
        select(DailyTask).where(DailyTask.uid == user.id, DailyTask.date == today)
    ).all()
    if tasks:
        return tasks

    chosen = random.sample(TASK_POOL, min(TASKS_PER_DAY, len(TASK_POOL)))
    tasks = [DailyTask(uid=user.id, date=today, description=text, points=TASK_POINTS) for text in chosen]
    for task in tasks:
        db.add(task)
    db.commit()
    for task in tasks:
        db.refresh(task)
    return tasks
