"""
Цели и мечты.
Мечта — это цель верхнего уровня (parent_id = None).
Обычная цель привязана к мечте через parent_id, состоит из шагов.
"""

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Form, Request
from sqlmodel import Session, select

from app.auth import require_user
from app.database import get_session
from app.models import Education, Goal, GoalHistory, GoalStep, Training, User
from app.rendering import render
from app.services.achievements import check_and_award_achievements
from app.services.flash import push_flash
from app.services.points import award_points, points_for_goal_difficulty
from app.services.progress import dream_progress_percent, goal_progress_percent

router = APIRouter()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _goals_context(db: Session, user: User, error: str = None) -> dict:
    """Собирает мечты пользователя вместе с их дочерними целями и прогрессом."""
    dreams = db.exec(
        select(Goal).where(Goal.uid == user.id, Goal.parent_id == None)  # noqa: E711
    ).all()

    dreams_with_children = []
    for dream in dreams:
        children = db.exec(select(Goal).where(Goal.parent_id == dream.id)).all()
        children_with_progress = [
            {"goal": g, "progress": goal_progress_percent(db, g)} for g in children
        ]
        dreams_with_children.append(
            {
                "dream": dream,
                "children": children_with_progress,
                "progress": dream_progress_percent(db, dream),
            }
        )

    return {"user": user, "dreams": dreams_with_children, "error": error, "today": date.today()}


@router.get("/goals")
def goals_list(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    """Список мечт и целей пользователя."""
    return render(request, "goals.html", _goals_context(db, user), db=db, user=user)


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
    return render(request, "goals.html", _goals_context(db, user), db=db, user=user)


@router.post("/goals/{dream_id}/child")
def create_goal(
    dream_id: int,
    request: Request,
    name: str = Form(...),
    description: str = Form(None),
    deadline: date = Form(None),
    difficulty: str = Form("medium"),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """Создаёт цель, привязанную к мечте. Очки по сложности считает сервер."""
    dream = db.get(Goal, dream_id)
    if not dream or dream.uid != user.id:
        return render(
            request, "goals.html", _goals_context(db, user, "Мечта не найдена"), db=db, user=user, status_code=404
        )

    if deadline and deadline < date.today():
        return render(
            request,
            "goals.html",
            _goals_context(db, user, "Дедлайн не может быть в прошлом"),
            db=db,
            user=user,
            status_code=400,
        )

    goal = Goal(
        uid=user.id,
        name=name,
        description=description,
        deadline=deadline,
        point=points_for_goal_difficulty(difficulty),
        story_point=1.0,
        parent_id=dream_id,
    )
    db.add(goal)
    user.goals += 1
    db.add(user)
    db.commit()
    return render(request, "goals.html", _goals_context(db, user), db=db, user=user)


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
    """Страница одной цели: описание, дедлайн, шаги, прогресс, история, программы."""
    goal = _get_owned_goal(db, goal_id, user)
    if not goal:
        return render(
            request, "goals.html", _goals_context(db, user, "Цель не найдена"), db=db, user=user, status_code=404
        )

    history = db.exec(
        select(GoalHistory).where(GoalHistory.h_id == goal_id).order_by(GoalHistory.time.desc())
    ).all()
    steps = db.exec(select(GoalStep).where(GoalStep.goal_id == goal_id)).all()
    trainings = db.exec(select(Training).where(Training.g_id == goal_id)).all()
    educations = db.exec(select(Education).where(Education.g_id == goal_id)).all()

    return render(
        request,
        "goal_detail.html",
        {
            "user": user,
            "goal": goal,
            "history": history,
            "steps": steps,
            "progress": goal_progress_percent(db, goal),
            "trainings": trainings,
            "educations": educations,
        },
        db=db,
        user=user,
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
        return render(
            request, "goals.html", _goals_context(db, user, "Цель не найдена"), db=db, user=user, status_code=404
        )

    db.add(GoalHistory(h_id=goal_id, time=_now()))
    db.commit()
    return goal_detail(goal_id, request, user, db)


@router.post("/goals/{goal_id}/steps")
def add_step(
    goal_id: int,
    request: Request,
    name: str = Form(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """Добавляет шаг внутри цели."""
    goal = _get_owned_goal(db, goal_id, user)
    if goal:
        db.add(GoalStep(goal_id=goal_id, name=name))
        db.commit()
    return goal_detail(goal_id, request, user, db)


@router.post("/goals/{goal_id}/steps/{step_id}/toggle")
def toggle_step(
    goal_id: int,
    step_id: int,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """Переключает шаг цели выполнен/не выполнен."""
    goal = _get_owned_goal(db, goal_id, user)
    step = db.get(GoalStep, step_id)
    if goal and step and step.goal_id == goal_id:
        step.done = not step.done
        db.add(step)
        if step.done:
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
        return render(
            request, "goals.html", _goals_context(db, user, "Цель не найдена"), db=db, user=user, status_code=404
        )

    if goal.status != "completed":
        goal.status = "completed"
        db.add(goal)
        db.add(GoalHistory(h_id=goal_id, time=_now()))
        db.commit()

        points = int(goal.point * goal.story_point)
        level, leveled_up = award_points(db, user, points)
        push_flash(request, f"+{points} очков 🎉 Цель выполнена!")
        if leveled_up:
            push_flash(request, f"⭐ Новый уровень: «{level.name}»!", "level-up")

        newly_earned = check_and_award_achievements(db, user)
        for achievement in newly_earned:
            push_flash(request, f"{achievement.icon} Новое достижение: «{achievement.name}»!", "achievement")

    return goal_detail(goal_id, request, user, db)
