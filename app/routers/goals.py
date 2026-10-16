"""
Цели и мечты.
Мечта — это цель верхнего уровня (parent_id = None).
Обычная цель привязана к мечте через parent_id.
"""

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Form, Request
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.auth import require_user
from app.database import get_session
from app.models import Education, Goal, GoalHistory, Training, User
from app.services.points import award_points

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _goals_context(db: Session, user: User, error: str = None) -> dict:
    """Собирает мечты пользователя вместе с их дочерними целями."""
    dreams = db.exec(
        select(Goal).where(Goal.uid == user.id, Goal.parent_id == None)  # noqa: E711
    ).all()

    dreams_with_children = []
    for dream in dreams:
        children = db.exec(select(Goal).where(Goal.parent_id == dream.id)).all()
        dreams_with_children.append({"dream": dream, "children": children})

    return {"user": user, "dreams": dreams_with_children, "error": error}


@router.get("/goals")
def goals_list(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    """Список мечт и целей пользователя."""
    return templates.TemplateResponse(request, "goals.html", _goals_context(db, user))


@router.post("/goals")
def create_dream(
    request: Request,
    name: str = Form(...),
    description: str = Form(None),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """Создаёт новую мечту (цель верхнего уровня)."""
    dream = Goal(uid=user.id, name=name, description=description, parent_id=None)
    db.add(dream)
    user.goals += 1
    db.add(user)
    db.commit()
    return templates.TemplateResponse(request, "goals.html", _goals_context(db, user))


@router.post("/goals/{dream_id}/child")
def create_goal(
    dream_id: int,
    request: Request,
    name: str = Form(...),
    description: str = Form(None),
    deadline: date = Form(None),
    point: int = Form(50),
    story_point: float = Form(1.0),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """Создаёт цель, привязанную к мечте."""
    dream = db.get(Goal, dream_id)
    if not dream or dream.uid != user.id:
        return templates.TemplateResponse(
            request, "goals.html", _goals_context(db, user, "Мечта не найдена"), status_code=404
        )

    goal = Goal(
        uid=user.id,
        name=name,
        description=description,
        deadline=deadline,
        point=point,
        story_point=story_point,
        parent_id=dream_id,
    )
    db.add(goal)
    user.goals += 1
    db.add(user)
    db.commit()
    return templates.TemplateResponse(request, "goals.html", _goals_context(db, user))


def _get_owned_goal(db: Session, goal_id: int, user: User) -> Goal | None:
    goal = db.get(Goal, goal_id)
    if not goal or goal.uid != user.id:
        return None
    return goal


@router.get("/goals/{goal_id}")
def goal_detail(
    goal_id: int,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """Страница одной цели: описание, дедлайн, история прогресса."""
    goal = _get_owned_goal(db, goal_id, user)
    if not goal:
        return templates.TemplateResponse(
            request, "goals.html", _goals_context(db, user, "Цель не найдена"), status_code=404
        )

    history = db.exec(
        select(GoalHistory).where(GoalHistory.h_id == goal_id).order_by(GoalHistory.time.desc())
    ).all()
    trainings = db.exec(select(Training).where(Training.g_id == goal_id)).all()
    educations = db.exec(select(Education).where(Education.g_id == goal_id)).all()

    return templates.TemplateResponse(
        request,
        "goal_detail.html",
        {
            "user": user,
            "goal": goal,
            "history": history,
            "trainings": trainings,
            "educations": educations,
        },
    )


@router.post("/goals/{goal_id}/progress")
def goal_progress(
    goal_id: int,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """Отмечает прогресс по цели (добавляет запись в историю)."""
    goal = _get_owned_goal(db, goal_id, user)
    if not goal:
        return templates.TemplateResponse(
            request, "goals.html", _goals_context(db, user, "Цель не найдена"), status_code=404
        )

    db.add(GoalHistory(h_id=goal_id, time=_now()))
    db.commit()
    return goal_detail(goal_id, request, user, db)


@router.post("/goals/{goal_id}/complete")
def goal_complete(
    goal_id: int,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """Завершает цель и начисляет очки."""
    goal = _get_owned_goal(db, goal_id, user)
    if not goal:
        return templates.TemplateResponse(
            request, "goals.html", _goals_context(db, user, "Цель не найдена"), status_code=404
        )

    if goal.status != "completed":
        goal.status = "completed"
        db.add(goal)
        db.add(GoalHistory(h_id=goal_id, time=_now()))
        db.commit()
        award_points(db, user, int(goal.point * goal.story_point))

    return goal_detail(goal_id, request, user, db)
