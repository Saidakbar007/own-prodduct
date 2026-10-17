"""
Друзья: заявка → принятие/отклонение, прогресс друга (уровень и streak),
рейтинг среди друзей по очкам за неделю.
"""

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Form, Request
from sqlmodel import Session, select

from app.auth import require_user
from app.database import get_session
from app.models import Friend, Habit, HabitConfirmation, HabitHistory, Level, PointsLog, User
from app.rendering import render
from app.services.achievements import check_and_award_achievements
from app.services.adaptive_plan import weekly_completion_rate
from app.services.flash import push_flash
from app.services.streak import best_streak_for_user

router = APIRouter()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _weekly_points(db: Session, uid: int) -> int:
    week_ago = date.today() - timedelta(days=6)
    logs = db.exec(select(PointsLog).where(PointsLog.uid == uid)).all()
    return sum(log.points for log in logs if log.time.date() >= week_ago)


def _weekly_completion_percent(db: Session, uid: int) -> int:
    """
    % выполнения за неделю — средняя доля отмеченных дней по всем привычкам
    пользователя. Рейтинг друзей считается по этому и по streak, а не по
    XP — иначе выигрывал бы тот, у кого просто больше/сложнее привычек.
    """
    habits = db.exec(select(Habit).where(Habit.uid == uid)).all()
    if not habits:
        return 0
    rates = [weekly_completion_rate(db, habit) for habit in habits]
    return round(sum(rates) / len(rates) * 100)


def _friend_card(db: Session, user_id: int) -> dict:
    """Публичные данные о прогрессе пользователя: уровень + лучший streak + % за неделю."""
    friend_user = db.get(User, user_id)
    level = db.exec(select(Level).where(Level.uid == user_id)).first()
    return {
        "user": friend_user,
        "level_name": level.name if level else "Новичок",
        "points": level.point if level else 0,
        "streak": best_streak_for_user(db, user_id),
        "weekly_points": _weekly_points(db, user_id),
        "weekly_completion_percent": _weekly_completion_percent(db, user_id),
        "trust_score": friend_user.trust_score if friend_user else 100,
    }


def _activity_feed(db: Session, user: User, friend_ids: list) -> list:
    """Лента последних отметок друзей (за 3 дня) — для подтверждения/сомнения."""
    if not friend_ids:
        return []

    habits = db.exec(select(Habit).where(Habit.uid.in_(friend_ids))).all()
    habit_by_id = {h.id: h for h in habits}
    if not habit_by_id:
        return []

    cutoff = _now() - timedelta(days=3)
    entries = db.exec(
        select(HabitHistory)
        .where(
            HabitHistory.h_id.in_(habit_by_id.keys()),
            HabitHistory.kind.in_(["done", "minimal"]),
            HabitHistory.time >= cutoff,
        )
        .order_by(HabitHistory.time.desc())
    ).all()

    feed = []
    for entry in entries[:20]:
        habit = habit_by_id[entry.h_id]
        owner = db.get(User, habit.uid)
        my_confirmation = db.exec(
            select(HabitConfirmation).where(
                HabitConfirmation.history_id == entry.id, HabitConfirmation.confirmer_uid == user.id
            )
        ).first()
        feed.append(
            {
                "entry": entry,
                "habit": habit,
                "owner": owner,
                "my_status": my_confirmation.status if my_confirmation else None,
            }
        )
    return feed


def _friends_context(db: Session, user: User, error: str = None) -> dict:
    accepted = db.exec(
        select(Friend).where(
            Friend.status == "accepted",
            (Friend.uid == user.id) | (Friend.friend_id == user.id),
        )
    ).all()
    friend_ids = [f.friend_id if f.uid == user.id else f.uid for f in accepted]
    friends = [_friend_card(db, fid) for fid in friend_ids]

    leaderboard = [_friend_card(db, user.id)] + friends
    # рейтинг по % выполнения за неделю и streak, а не по XP — иначе игра
    # в "накопить побольше очков" вытеснила бы стабильность выполнения
    leaderboard.sort(key=lambda c: (c["weekly_completion_percent"], c["streak"]), reverse=True)

    incoming = db.exec(
        select(Friend).where(Friend.friend_id == user.id, Friend.status == "pending")
    ).all()
    outgoing = db.exec(
        select(Friend).where(Friend.uid == user.id, Friend.status == "pending")
    ).all()

    return {
        "user": user,
        "friends": friends,
        "leaderboard": leaderboard,
        "incoming": incoming,
        "outgoing": outgoing,
        "feed": _activity_feed(db, user, friend_ids),
        "error": error,
    }


@router.get("/friends")
def friends_list(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    """Список друзей, рейтинг за неделю, входящие и исходящие заявки."""
    return render(request, "friends.html", _friends_context(db, user), db=db, user=user)


@router.post("/friends/request")
def send_request(
    request: Request,
    login: str = Form(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """Отправляет заявку в друзья по логину."""
    target = db.exec(select(User).where(User.login == login)).first()

    if not target or target.id == user.id:
        return render(
            request, "friends.html", _friends_context(db, user, "Пользователь не найден"), db=db, user=user, status_code=404
        )

    existing = db.exec(
        select(Friend).where(
            ((Friend.uid == user.id) & (Friend.friend_id == target.id))
            | ((Friend.uid == target.id) & (Friend.friend_id == user.id))
        )
    ).first()
    if existing:
        return render(
            request,
            "friends.html",
            _friends_context(db, user, "Заявка уже существует или вы уже друзья"),
            db=db,
            user=user,
            status_code=400,
        )

    db.add(Friend(uid=user.id, friend_id=target.id, status="pending"))
    db.commit()
    return render(request, "friends.html", _friends_context(db, user), db=db, user=user)


@router.post("/friends/{friend_id}/accept")
def accept_request(
    friend_id: int,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """Принимает заявку в друзья. Принять может только адресат заявки."""
    friend = db.get(Friend, friend_id)
    if friend and friend.friend_id == user.id and friend.status == "pending":
        friend.status = "accepted"
        friend.update_date = _now()
        db.add(friend)
        db.commit()

        newly_earned = check_and_award_achievements(db, user)
        for achievement in newly_earned:
            push_flash(request, f"{achievement.icon} Новое достижение: «{achievement.name}»!", "achievement")

        other_user = db.get(User, friend.uid)
        if other_user:
            check_and_award_achievements(db, other_user)

    return render(request, "friends.html", _friends_context(db, user), db=db, user=user)


@router.post("/friends/{friend_id}/decline")
def decline_request(
    friend_id: int,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """Отклоняет заявку в друзья. Отклонить может только адресат заявки."""
    friend = db.get(Friend, friend_id)
    if friend and friend.friend_id == user.id and friend.status == "pending":
        friend.status = "declined"
        friend.update_date = _now()
        db.add(friend)
        db.commit()
    return render(request, "friends.html", _friends_context(db, user), db=db, user=user)
