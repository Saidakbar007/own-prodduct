"""
Ставки: поставить очки на выполнение привычки N дней подряд.
Выиграл — ×2, проиграл — очки не возвращаются (списаны при создании ставки).
"""

from datetime import date

from sqlmodel import Session, select

from app.models import Bet, Habit, HabitHistory, Level, User
from app.services.points import award_points
from app.services.streak import consecutive_run_from


def place_bet(db: Session, user: User, habit: Habit, stake_points: int, target_days: int) -> Bet | None:
    """Создаёт ставку, списывая очки сразу. Возвращает None, если очков не хватает."""
    level = db.exec(select(Level).where(Level.uid == user.id)).first()
    if not level or level.point < stake_points or stake_points <= 0:
        return None

    level.point -= stake_points
    db.add(level)

    bet = Bet(
        uid=user.id,
        habit_id=habit.id,
        stake_points=stake_points,
        target_days=target_days,
        start_date=date.today(),
        status="active",
    )
    db.add(bet)
    db.commit()
    db.refresh(bet)
    return bet


def evaluate_bet(db: Session, bet: Bet) -> Bet:
    """Проверяет активную ставку: выиграна, проиграна или ещё идёт."""
    if bet.status != "active":
        return bet

    history = db.exec(select(HabitHistory).where(HabitHistory.h_id == bet.habit_id)).all()
    done_dates = {h.time.date() for h in history if h.kind in ("done", "minimal")}

    length, broken = consecutive_run_from(done_dates, bet.start_date, date.today())

    if length >= bet.target_days:
        bet.status = "won"
        db.add(bet)
        db.commit()
        user = db.get(User, bet.uid)
        award_points(db, user, bet.stake_points * 2, apply_trust=False)
    elif broken:
        bet.status = "lost"
        db.add(bet)
        db.commit()

    return bet


def evaluate_bets_for_habit(db: Session, habit_id: int) -> None:
    """Проверяет все активные ставки на эту привычку (вызывается после отметки)."""
    bets = db.exec(select(Bet).where(Bet.habit_id == habit_id, Bet.status == "active")).all()
    for bet in bets:
        evaluate_bet(db, bet)
