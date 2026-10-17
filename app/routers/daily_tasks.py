"""
Отметка выполнения ежедневного мини-задания.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.auth import require_user
from app.database import get_session
from app.models import DailyTask, User
from app.services.achievements import check_and_award_achievements
from app.services.coins import DAILY_TASK_ALL_THREE_BONUS, DAILY_TASK_COINS, award_coins
from app.services.flash import push_flash
from app.services.levels import level_for_xp, level_up_message
from app.services.points import award_points

router = APIRouter()


@router.post("/daily-tasks/{task_id}/complete")
def complete_task(
    task_id: int,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """Отмечает ежедневное задание выполненным и начисляет бонусные очки и монеты."""
    task = db.get(DailyTask, task_id)
    if task and task.uid == user.id and not task.done:
        task.done = True
        db.add(task)
        db.commit()

        level, leveled_up = award_points(db, user, task.points)
        push_flash(request, f"+{task.points} бонусных очков за задание 🎉")
        if leveled_up:
            push_flash(request, level_up_message(level_for_xp(level.point)), "level-up")

        coin_amount = DAILY_TASK_COINS
        today_tasks = db.exec(select(DailyTask).where(DailyTask.uid == user.id, DailyTask.date == task.date)).all()
        if today_tasks and all(t.done for t in today_tasks):
            coin_amount += DAILY_TASK_ALL_THREE_BONUS
        awarded_coins = award_coins(db, user, coin_amount)
        if awarded_coins:
            push_flash(request, f"+{awarded_coins} 🪙", "coins")

        newly_earned = check_and_award_achievements(db, user)
        for achievement in newly_earned:
            push_flash(request, f"{achievement.icon} Новое достижение: «{achievement.name}»!", "achievement")

    return RedirectResponse("/", status_code=303)
