"""
Прогресс по целям (v2): считается по доле выполненных шагов.
Прогресс мечты = средний прогресс её целей.
"""

from sqlmodel import Session, select

from app.models import Goal, GoalStep


def goal_progress_percent(db: Session, goal: Goal) -> int:
    """Процент выполнения одной цели: завершённая цель — 100%, иначе по шагам."""
    if goal.status == "completed":
        return 100

    steps = db.exec(select(GoalStep).where(GoalStep.goal_id == goal.id)).all()
    if not steps:
        return 0

    done = sum(1 for s in steps if s.done)
    return int(done / len(steps) * 100)


def dream_progress_percent(db: Session, dream: Goal) -> int:
    """Прогресс мечты = среднее арифметическое прогресса её целей (0, если целей нет)."""
    children = db.exec(select(Goal).where(Goal.parent_id == dream.id)).all()
    if not children:
        return 0
    return int(sum(goal_progress_percent(db, c) for c in children) / len(children))
