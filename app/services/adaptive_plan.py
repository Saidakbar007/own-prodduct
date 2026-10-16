"""
Адаптивный план: если за неделю выполнено < 50% отметок привычки,
предлагается урезанный план (daily -> weekly, 3 дня в неделю).
"""

import os
from datetime import date, timedelta

from sqlmodel import Session, select

from app.models import Habit, HabitHistory

WEEKLY_FALLBACK_DAYS = "0,2,4"  # Пн/Ср/Пт — по умолчанию урезанный план


def weekly_completion_rate(db: Session, habit: Habit) -> float:
    """Доля дней за последние 7, когда привычка была отмечена (done/minimal)."""
    week_ago = date.today() - timedelta(days=6)
    history = db.exec(select(HabitHistory).where(HabitHistory.h_id == habit.id)).all()
    done_dates = {h.time.date() for h in history if h.kind in ("done", "minimal") and h.time.date() >= week_ago}
    return len(done_dates) / 7


def needs_adaptive_plan(db: Session, habit: Habit) -> bool:
    """Нужен ли урезанный план (выполнение за неделю < 50%)."""
    return habit.frequency == "daily" and weekly_completion_rate(db, habit) < 0.5


def adaptive_plan_message(habit: Habit) -> str:
    """Текст предложения урезанного плана — через Claude API, если есть ключ, иначе по правилам."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=150,
                messages=[{
                    "role": "user",
                    "content": (
                        f"Пользователь выполняет привычку «{habit.name}» реже 50% дней за неделю. "
                        "Мягко, без вины, предложи перейти на урезанный план — делать это 3 раза "
                        "в неделю (пн/ср/пт) вместо каждого дня. 2-3 предложения на русском."
                    ),
                }],
            )
            return response.content[0].text
        except Exception:
            pass

    return (
        f"Похоже, «{habit.name}» в последнее время даётся тяжело — и это нормально. "
        "Может, пока перейти на 3 дня в неделю (пн/ср/пт) вместо каждого дня? "
        "Серию это не прервёт, а вернуться к ежедневному режиму можно в любой момент."
    )


def apply_adaptive_plan(db: Session, habit: Habit) -> Habit:
    """Применяет урезанный план: daily -> weekly (пн/ср/пт)."""
    habit.frequency = "weekly"
    habit.weekdays = WEEKLY_FALLBACK_DAYS
    db.add(habit)
    db.commit()
    db.refresh(habit)
    return habit
