"""
Тренировочные (Training) и образовательные (Education) программы,
привязанные к конкретной цели.
"""

from fastapi import APIRouter, Depends, Form, Request
from sqlmodel import Session

from app.auth import require_user
from app.database import get_session
from app.models import Education, Goal, Training, User

router = APIRouter()


def _goal_owned_by(db: Session, goal_id: int, user: User) -> Goal | None:
    goal = db.get(Goal, goal_id)
    if not goal or goal.uid != user.id:
        return None
    return goal


@router.post("/goals/{goal_id}/training")
def add_training(
    goal_id: int,
    request: Request,
    name: str = Form(...),
    program: str = Form(None),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """Добавляет тренировочную программу к цели."""
    goal = _goal_owned_by(db, goal_id, user)
    if goal:
        db.add(Training(uid=user.id, g_id=goal_id, name=name, program=program))
        db.commit()

    from app.routers.goals import goal_detail

    return goal_detail(goal_id, request, user, db)


@router.post("/goals/{goal_id}/education")
def add_education(
    goal_id: int,
    request: Request,
    name: str = Form(...),
    program: str = Form(None),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """Добавляет образовательную программу к цели."""
    goal = _goal_owned_by(db, goal_id, user)
    if goal:
        db.add(Education(uid=user.id, g_id=goal_id, name=name, program=program))
        db.commit()

    from app.routers.goals import goal_detail

    return goal_detail(goal_id, request, user, db)
